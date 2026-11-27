import base64
import hashlib
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

import ollama

import config

REFUSAL = "Я не могу выдать эту информацию. Могу помочь с открытыми материалами проекта."
NO_CONTEXT = "В доступных документах не нашлось информации для ответа."
CANARY = r"CANARY[-‐‑–]"
CONFIDENTIAL = r"(?<![а-яё])конфиденциально(?![а-яё])"
TOKEN_VALUE = r"""\s*[:=]\s*['"]?[\w./+=-]{4,}"""

# Секреты ищем даже рядом с открытыми контактами.
SECRET_RULES = [
    ("canary", CANARY),
    ("token", r"\b(?:sk-|ghp_|github_pat_|hf_|glpat-|xox[baprs]-)[\w-]{6,}"),  # Известные префиксы
    ("token", r"\bAKIA[A-Z0-9]{16}"),  # Ключи AWS
    ("token", r"\bBearer\s+[A-Za-z0-9._~+/=-]{6,}"),  # Токен авторизации
    ("token", r"\b(?:demo|test)[_-]token[_-][\w-]+"),  # Учебные токены
    ("token", r"\b(?:api[_ -]?key|(?:[\w-]+[_ -])?token)" + TOKEN_VALUE),  # Например, API_TOKEN=...
    ("token", r"\b(?:токен|пароль)" + TOKEN_VALUE),
    ("salary", r"(?:зарплат\w*|оклад\w*|salary)[^\n.!?]{0,45}\d[\d \u00a0.,]*\d"),  # Оклад с суммой
]
ID_RULES = [
    ("snils", r"(?<!\d)\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}(?!\d)"),
    ("passport", r"(?<!\d)(?:\d{2}[ -]\d{2}|\d{4})[ -]+\d{6}(?!\d)"),
    ("inn", r"(?<!\d)(?:\d{10}|\d{12})(?!\d)"),
]
CONTACT_RULES = [
    ("email", r"[\w.+-]+@[\w.-]+\.[a-zа-я]{2,}"),
    ("phone", r"(?<!\w)(?:\+7|8)[ (.-]*\d{3}[ ).-]*\d{3}[ .-]*\d{2}[ .-]*\d{2}(?!\d)"),
]
PUBLIC_LABELS = (
    "техподдерж", "технической поддержки", "поддержка:", "поддержки:", "отдела кадров",
    "служба поддержки", "службы поддержки", "телефон поддержки",
    "горячая линия", "горячей линии", "общий телефон", "общая почта",
    "контакты компании", "публичные контакты", "приёмная", "приемная", "support:", "help desk:",
)
PUBLIC_MAILBOXES = ("support", "help", "hr-help", "helpdesk", "info", "office", "contact", "sales")
PRIVATE_LABELS = [
    r"\b(?:личн|домашн|персональн|закрыт)\w*\b",
    r"\b(?:personal|private)\b",
    r"\b(?:снилс|инн|паспорт\w*)\b",
]

# Вопросы о системных инструкциях, личных данных и темы вне учебной базы.
PROMPT_RULES = [
    r"system[\s_-]*(?:prompt|instructions?|message)",
    r"системн\w*\s+(?:промпт|инструкц|сообщени)",
]
REQUEST_STARTS = (
    "покаж", "вывед", "вывес", "верн", "повтор", "напечат", "скопир", "назов", "раскр",
    "процитир", "пришл", "сообщи", "дай", "какой", "какая", "какие", "каков", "каковы",
    "show", "print", "repeat", "reveal", "return", "quote", "give", "tell",
)
OWN_PROMPT = r"(?:какой|какие|каков|каковы)\s+(?:у тебя|твой|твои|ваш)|what(?: is|'s| are) your"
PRIVATE_REQUESTS = [
    r"\b(?:снилс|инн|паспорт\w*)\b",
    r"\b(?:токен\w*|парол\w*|зарплат\w*|оклад\w*|личн\w*\s+контакт\w*)\b",
    r"\b(?:salary|passport|access token)\b",
]
OFF_TOPIC = [
    r"\bпогод[аеуы]\b",
    r"\bкто выиграл\b[^\n.!?]{0,25}\b(?:матч|чемпионат)",
    r"\bфутбольн\w*\s+матч\w*",
    r"\bweather forecast\b",
]

# Ищем указания модели внутри документов, до вызова Qwen.
DOCUMENT_ORDERS = [
    r"инструкци\w* для (?:модели|ассистента)",
    r"(?:ассистент|модель)\s*[:,]\s*(?:игнорируй|отвечай)",
    r"игнорируй\s+(?:все\s+)?предыдущие\s+инструкции",
    r"(?:ignore|disregard)\s+(?:all\s+)?(?:previous|prior)\s+instructions",
    r"<\|im_start\|>\s*system",
]


def matches(text, patterns):
    for pattern in patterns:
        if re.search(pattern, text, re.I):
            return True
    return False


def contact_key(kind, value):
    if kind == "phone":
        # +7 и 8 в начале — две записи одного и того же номера.
        digits = re.sub(r"\D", "", value)
        return "7" + digits[1:]
    return value.lower()


def public_contacts(text):
    # Вызываем только для открытого чанка. Берём общие контакты организации.
    contacts = set()
    heading = ""
    for line in text.splitlines():
        label = line.strip().lower()
        if not label or label.endswith(":"):
            heading = label
        labels = heading + " " + label
        if matches(labels, PRIVATE_LABELS):
            continue
        business = any(label in labels for label in PUBLIC_LABELS)
        for kind, pattern in CONTACT_RULES:
            for value in re.findall(pattern, line, re.I):
                work_email = kind == "email" and value.lower().split("@")[0] in PUBLIC_MAILBOXES
                if business or work_email:
                    contacts.add(contact_key(kind, value))
    return contacts


def data_reason(text, allowed_contacts=()):
    for reason, pattern in SECRET_RULES:
        if re.search(pattern, text, re.I):
            return reason

    # Скрываем подтверждённые контакты только для проверки форматов PII.
    # Иначе телефон из 11 цифр может совпасть с форматом СНИЛС.
    lines = []
    contact_reason = ""
    heading = ""
    for line in text.splitlines(keepends=True):
        if not line.strip() or line.rstrip().endswith(":"):
            heading = line.strip()
        checked = line
        personal = matches(heading + " " + line, PRIVATE_LABELS)
        for kind, pattern in CONTACT_RULES:
            for match in re.finditer(pattern, line, re.I):
                key = contact_key(kind, match.group())
                if not personal and key in allowed_contacts:
                    start, end = match.span()
                    checked = checked[:start] + " " * (end - start) + checked[end:]
                elif not contact_reason:
                    contact_reason = kind
        lines.append(checked)

    checked_text = "".join(lines)
    for reason, pattern in ID_RULES:
        if re.search(pattern, checked_text):
            return reason
    return contact_reason


def obvious_base64(text):
    # Пометка с данными, длинная строка или короткая строка с "=" в конце.
    if re.search(r"\bbase64\s*[:,=]\s*[A-Za-z0-9+/_-]{4,}", text, re.I):
        return True
    tokens = re.findall(r"(?<![\w/-])[A-Za-z0-9+/_-]{20,}={0,2}(?![\w/-])", text)
    tokens += re.findall(r"\bbase64\s+([A-Za-z0-9+/_-]{4,}={0,2})", text, re.I)
    text = text.strip()
    if re.fullmatch(r"[A-Za-z0-9+/_-]{4,}={1,2}", text):
        tokens.append(text)

    for token in tokens:
        while len(token) % 4 != 0:
            token += "="
        try:
            decoded = base64.b64decode(token, altchars=b"-_", validate=True).decode("utf-8")
        except ValueError:
            continue
        if not decoded:
            continue
        printable = True
        for char in decoded:
            if not char.isprintable() and not char.isspace():
                printable = False
                break
        if printable:
            return True
    return False


def llama_reason(messages):
    response = ollama.chat(
        model=config.GUARD_MODEL,
        messages=messages,
        stream=False,
        keep_alive=0,
        options={"num_ctx": config.NUM_CTX, "num_predict": 32, "temperature": 0},
    )
    verdict = response["message"]["content"].strip().lower()
    if verdict == "safe":
        return ""
    lines = verdict.splitlines()
    if lines and lines[0].strip() == "unsafe":
        return "llama_guard"
    raise ValueError("Гард не вернул метку safe/unsafe.")


def input_reason(question):
    if obvious_base64(question):
        return "base64"
    request = False
    for word in re.findall(r"\w+", question.lower()):
        if word.startswith(REQUEST_STARTS):
            request = True
            break
    if matches(question, PROMPT_RULES):
        if request or re.search(OWN_PROMPT, question, re.I):
            return "system_prompt_request"
    if request and matches(question, PRIVATE_REQUESTS):
        return "private_request"
    if matches(question, OFF_TOPIC):
        return "off_topic"
    reason = data_reason(question)
    if reason:
        return reason
    return llama_reason([{"role": "user", "content": question}])


def private_document(filename, text):
    name = Path(filename.replace("\\", "/")).name
    if name.lower().startswith("private"):
        return True
    return matches(name + "\n" + text, [CONFIDENTIAL, CANARY])


def context_reason(doc):
    # В старой базе без этой метки статус файла неизвестен.
    if doc.metadata.get("private_file") is not False:
        return "private_document"
    name = doc.metadata.get("file_name") or doc.metadata.get("source", "")
    name = Path(name.replace("\\", "/")).name
    if not name or private_document(name, doc.page_content):
        return "private_document"
    if matches(doc.page_content, DOCUMENT_ORDERS):
        return "instruction_in_document"
    return data_reason(name + "\n" + doc.page_content, public_contacts(doc.page_content))


def prompt_fragment(answer):
    words = re.findall(r"\w+", config.SYSTEM_PROMPT.lower())
    if not words:
        return False
    # Сравниваем пять соседних слов. Пробелы по краям отделяют целые слова.
    answer_words = re.findall(r"\w+", answer.lower())
    answer_text = " " + " ".join(answer_words) + " "
    size = min(5, len(words))
    for i in range(len(words) - size + 1):
        fragment = " ".join(words[i : i + size])
        if f" {fragment} " in answer_text:
            return True
    return False


def output_reason(question, answer, allowed_contacts=()):
    reason = data_reason(answer, allowed_contacts)
    if reason:
        return reason
    if prompt_fragment(answer):
        return "system_prompt_fragment"
    messages = [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ]
    return llama_reason(messages)


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_log(question, info):
    row = {"timestamp_ms": int(time.time() * 1000), "question_sha256": sha256(question)}
    row.update(info)
    config.AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with config.AUDIT_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")


def prepare_guard():
    # Исправляем последнюю строку шаблона. Она должна выбирать User или Agent.
    template = ollama.show(config.GUARD_BASE)["template"]
    if "$role :=" not in template:
        raise ValueError("Не найден выбор роли в шаблоне Llama Guard.")
    old = "ONLY THE LAST User message"
    new = "ONLY THE LAST {{ $role }} message"
    if old in template:
        template = template.replace(old, new)
    if new not in template:
        raise ValueError("Строка проверки роли в шаблоне Llama Guard изменилась.")

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "Modelfile"
        path.write_text(f'FROM {config.GUARD_BASE}\nTEMPLATE """{template}"""\n', encoding="utf-8")
        subprocess.run(["ollama", "create", config.GUARD_MODEL, "-f", str(path)], check=True)
    print("Гард готов:", config.GUARD_MODEL)


if __name__ == "__main__":
    prepare_guard()
