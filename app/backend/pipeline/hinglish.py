"""Conversational Hindi-to-Hinglish transliteration module.
Converts spoken Hindi transcribed in Devanagari into natural Latin script (Hinglish)
matching modern texting and YouTube/Instagram gaming subtitles:
e.g. "मैं यह खेल रहा हूँ" -> "mai yeh khel rha hu".
"""
import json
import re
import string

# Extensive dictionary of common conversational & gaming Hindi words
HINGLISH_DICT = {
    # Pronouns & pointers
    "मैं": "mai", "मै": "mai", "मुझे": "mujhe", "मुझको": "mujhko", "मेरा": "mera", "मेरी": "meri", "मेरे": "mere",
    "तू": "tu", "तुझे": "tujhe", "तुझको": "tujhko", "तेरा": "tera", "तेरी": "teri", "तेरे": "tere",
    "तुम": "tum", "तुम्हें": "tumhe", "तुम्हे": "tumhe", "तुमको": "tumko", "तुम्हारा": "tumhara", "तुम्हारी": "tumhari", "तुम्हारे": "tumhare",
    "आप": "aap", "आपको": "aapko", "आपका": "aapka", "आपकी": "aapki", "आपके": "aapke",
    "यह": "yeh", "ये": "yeh", "इस": "is", "इसे": "ise", "इसको": "isko", "इसका": "iska", "इसकी": "iski", "इसके": "iske", "इसमें": "isme",
    "वह": "woh", "वो": "woh", "उस": "us", "उसे": "use", "उसको": "usko", "उसका": "uska", "उसकी": "uski", "उसके": "uske", "उसमें": "usme",
    "हम": "hum", "हमें": "hume", "हमको": "humko", "हमारा": "hamara", "हमारी": "hamari", "हमारे": "hamare",
    "वे": "woh", "उन्हें": "unhe", "उनको": "unko", "उनका": "unka", "उनकी": "unki", "उनके": "unke",
    "अपना": "apna", "अपनी": "apni", "अपने": "apne",

    # Common verbs & auxiliaries
    "है": "hai", "हैं": "hain", "हूँ": "hu", "हूं": "hu", "हु": "hu", "हो": "ho",
    "था": "tha", "थी": "thi", "थे": "the",
    "रहा": "rha", "रहे": "rhe", "रही": "rhi",
    "खेल": "khel", "खेला": "khela", "खेलता": "khelta", "खेलते": "khelte", "खेलती": "khelti", "खेलेंगे": "khelenge",
    "कर": "kar", "करो": "karo", "करा": "kara", "किया": "kiya", "किए": "kiye", "की": "ki",
    "करेगा": "karega", "करेगी": "karegi", "करेंगे": "karenge", "करूंगा": "karunga", "करूंगी": "karungi", "करते": "karte", "करता": "karta", "करती": "karti",
    "जा": "ja", "जाओ": "jao", "जाता": "jaata", "जाती": "jaati", "जाते": "jaate", "जाएगा": "jaayega", "जाएगी": "jaayegi", "जाएंगे": "jaayenge",
    "गया": "gaya", "गई": "gayi", "गयी": "gayi", "गए": "gaye",
    "आ": "aa", "आओ": "aao", "आता": "aata", "आती": "aati", "आते": "aate", "आएगा": "aayega", "आएगी": "aayegi", "आएंगे": "aayenge",
    "आया": "aaya", "आई": "aayi", "आयी": "aayi", "आए": "aaye",
    "देख": "dekh", "देखो": "dekho", "देखा": "dekha", "देखे": "dekhe", "देखते": "dekhte", "देखता": "dekhta", "देखेंगे": "dekhenge",
    "बोल": "bol", "बोलो": "bolo", "बोला": "bola", "बोले": "bole", "बोलता": "bolta", "बोलते": "bolte", "बोलेंगे": "bolenge",
    "कह": "keh", "कहो": "kaho", "कहा": "kaha", "कहे": "kahe", "कहते": "kehte", "कहता": "kehta",
    "रुक": "ruk", "रुको": "ruko", "रुका": "ruka", "रुके": "ruke",
    "मार": "maar", "मारो": "maaro", "मारा": "maara", "मारे": "maare", "मारेंगे": "maarenge",
    "मर": "mar", "मरो": "maro", "मरा": "mara", "मरे": "mare",
    "जीत": "jeet", "जीतो": "jeeto", "जीता": "jeeta", "जीते": "jeete", "जीतेंगे": "jeetenge",
    "हार": "haar", "हरो": "haro", "हारा": "haara", "हारे": "haare",
    "सुन": "sun", "सुनो": "suno", "सुना": "suna", "सुने": "sune",
    "समझ": "samajh", "समझो": "samjho", "समझा": "samjha", "समझे": "samjhe",
    "बैठ": "baith", "बैठो": "baitho", "बैठा": "baitha", "बैठे": "baithe",
    "चल": "chal", "चलो": "chalo", "चला": "chala", "चले": "chale", "चलते": "chalte", "चलेगा": "chalega",
    "दे": "de", "दो": "do", "दिया": "diya", "दिए": "diye", "देगा": "dega", "देंगे": "denge",
    "ले": "le", "लो": "lo", "लिया": "liya", "लिए": "liye", "लेगा": "lega", "लेंगे": "lenge",
    "लग": "lag", "लगा": "laga", "लगे": "lage", "लगता": "lagta", "लगती": "lagti", "लगते": "lagte",
    "डाल": "daal", "डालो": "daalo", "डाला": "daala", "डाले": "daale",
    "उठा": "utha", "उठाओ": "uthao", "उठाया": "uthaya",
    "पकड़": "pakad", "पकड़ो": "pakdo", "पकड़ा": "pakda",
    "छोड़": "chhod", "छोड़ो": "chhodo", "छोड़ा": "chhoda",

    # Questions & Interrogatives
    "क्या": "kya", "क्यों": "kyu", "क्यो": "kyu", "क्योंकी": "kyuki", "क्योंकि": "kyunki",
    "कैसे": "kaise", "कैसा": "kaisa", "कैसी": "kaisi",
    "कब": "kab", "कहाँ": "kaha", "कहा": "kaha", "किधर": "kidhar", "कौन": "kaun",
    "कितना": "kitna", "कितनी": "kitni", "कितने": "kitne",

    # Prepositions & Connectors
    "में": "me", "मे": "me", "पे": "pe", "पर": "par", "से": "se", "को": "ko", "तक": "tak",
    "का": "ka", "की": "ki", "के": "ke",
    "और": "aur", "या": "ya", "लेकिन": "lekin", "परन्तु": "parantu", "मगर": "magar",
    "तो": "to", "भी": "bhi", "ही": "hi", "ना": "na", "ने": "ne",
    "क्योंकि": "kyunki", "ताकि": "taaki", "अगर": "agar", "यदि": "yadi",

    # Adverbs & Adjectives
    "हाँ": "haan", "हां": "haan", "नहीं": "nahi", "नही": "nahi", "मत": "mat",
    "बहुत": "bahut", "ज्यादा": "jyada", "कम": "kam", "थोड़ा": "thoda", "थोडा": "thoda",
    "अच्छा": "accha", "अच्छी": "acchi", "अच्छे": "acche", "बुरा": "bura", "बुरी": "buri", "बुरे": "bure",
    "सही": "sahi", "गलत": "galat", "सच": "sach", "झूठ": "jhooth",
    "जल्दी": "jaldi", "धीरे": "dheere", "तेज": "tez",
    "बड़ा": "bada", "बड़ी": "badi", "बड़े": "bade", "छोटा": "chota", "छोटी": "choti", "छोटे": "chote",
    "पूरा": "poora", "पूरी": "poori", "पूरे": "poore", "आधा": "aadha",
    "अभी": "abhi", "आज": "aaj", "कल": "kal", "परसों": "parso",
    "पहले": "pehle", "बाद": "baad", "फिर": "phir", "हमेशा": "hamesha", "कभी": "kabhi",
    "यहाँ": "yahan", "यहां": "yahan", "वहाँ": "wahan", "वहां": "wahan", "कही": "kahin", "कहीं": "kahin",
    "अंदर": "andar", "बाहर": "baahar", "ऊपर": "upar", "नीचे": "neeche", "आगे": "aage", "पीछे": "peeche",
    "पास": "paas", "दूर": "door", "साथ": "saath", "सामने": "saamne",
    "सब": "sab", "सभी": "sabhi", "लोग": "log", "कोई": "koi", "कुछ": "kuch", "हर": "har",
    "बस": "bas", "सिर्फ": "sirf", "केवल": "kewal",
    "शुरू": "shuru", "खत्म": "khatam", "बंद": "band", "चालू": "chalu",

    # Conversational Exclamations & Gamer slang
    "भाई": "bhai", "यार": "yaar", "अरे": "are", "अबे": "abe", "ओए": "oye", "सुन": "sun", "सुनो": "suno",
    "पता": "pata", "मालूम": "maloom", "बात": "baat", "काम": "kaam", "नाम": "naam",
    "आवाज": "awaaz", "टाइम": "time", "गेम": "game", "बंदा": "banda", "बंदे": "bande",
    "किल": "kill", "ओपी": "op", "हेडशॉट": "headshot", "नोब": "noob", "प्रो": "pro",
    "साला": "saala", "साले": "saale", "हैक": "hack", "हैकर": "hacker",
    "स्ट्रीम": "stream", "लाइव": "live", "चैट": "chat", "सर्वर": "server", "लैग": "lag",

    # Numbers
    "एक": "ek", "दो": "do", "तीन": "teen", "चार": "chaar", "पांच": "paanch",
    "छह": "che", "सात": "saat", "आठ": "aath", "नौ": "nau", "दस": "das",
}

# Phonetic Devanagari mappings for non-dictionary words
DEV_CONSONANTS = {
    'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'ng',
    'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'jh', 'ञ': 'ny',
    'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n',
    'त': 't', 'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n',
    'प': 'p', 'फ': 'ph', 'ब': 'b', 'भ': 'bh', 'म': 'm',
    'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v',
    'श': 'sh', 'ष': 'sh', 'स': 's', 'ह': 'h',
    'क़': 'q', 'ख़': 'kh', 'ग़': 'g', 'ज़': 'z', 'ड़': 'r', 'ढ़': 'rh', 'फ़': 'f',
    'क्ष': 'ksh', 'त्र': 'tr', 'ज्ञ': 'gya', 'श्र': 'shr'
}

DEV_VOWELS = {
    'अ': 'a', 'आ': 'aa', 'इ': 'i', 'ई': 'ee', 'उ': 'u', 'ऊ': 'oo', 'ऋ': 'ri',
    'ए': 'e', 'ऐ': 'ai', 'ओ': 'o', 'औ': 'au', 'अं': 'an', 'अः': 'ah'
}

DEV_MATRAS = {
    'ा': 'a', 'ि': 'i', 'ी': 'ee', 'ु': 'u', 'ू': 'oo', 'ृ': 'ri',
    'े': 'e', 'ै': 'ai', 'ो': 'o', 'ौ': 'au',
    'ं': 'n', 'ँ': 'n', 'ः': 'h'
}

CONSONANTS_SET = set(DEV_CONSONANTS.keys())
MATRAS_SET = set(DEV_MATRAS.keys())

def _phonetic_transliterate(word: str) -> str:
    """Phonetically transliterate a single Hindi word into natural Romanized Latin script."""
    chars = list(word)
    out = []
    n = len(chars)

    for i, c in enumerate(chars):
        if c in DEV_VOWELS:
            out.append(DEV_VOWELS[c])
        elif c in DEV_MATRAS:
            out.append(DEV_MATRAS[c])
        elif c in DEV_CONSONANTS:
            base = DEV_CONSONANTS[c]
            # Check next character to determine if inherent 'a' is sounded
            next_c = chars[i + 1] if i + 1 < n else None
            
            if next_c == '्':  # Halant suppresses 'a'
                out.append(base)
            elif next_c in MATRAS_SET:  # Matra replaces inherent 'a'
                out.append(base)
            elif next_c is None:  # Modern Hindi schwa deletion at word end: khel, not khela
                out.append(base)
            else:
                # Add inherent 'a' between consonants
                out.append(base + 'a')
        elif c == '्':
            continue
        elif c in ['।', '॥']:
            out.append('.')
        elif 0x0900 <= ord(c) <= 0x097F:
            # Drop any unmapped Devanagari marks to guarantee 100% English/Latin script
            continue
        else:
            out.append(c)

    res = ''.join(out)
    return res

def transliterate_to_hinglish(text: str) -> str:
    """
    Convert a text string (which may contain Devanagari Hindi, English, punctuation)
    into clean conversational Hinglish.
    Example:
        "मैं यह खेल रहा हूँ" -> "mai yeh khel rha hu"
    """
    if not text:
        return ""
    
    # Check if text contains Devanagari Unicode (0x0900 to 0x097F)
    if not any(0x0900 <= ord(c) <= 0x097F for c in text):
        return text

    # Split into tokens preserving punctuation and whitespace
    tokens = re.findall(r"[\w\u0900-\u097F]+|[^\w\s]|\s+", text, re.UNICODE)
    result = []

    for token in tokens:
        if any(0x0900 <= ord(c) <= 0x097F for c in token):
            # Check dictionary first
            if token in HINGLISH_DICT:
                result.append(HINGLISH_DICT[token])
            else:
                # Try phonetic transliteration
                result.append(_phonetic_transliterate(token))
        else:
            result.append(token)

    return "".join(result)


# ── High-quality batch transliteration (Gemini), with the rule-based converter as fallback ──
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_EDGE_PUNCT = "।॥,.!?\"'()…:;-"


def _has_devanagari(text: str) -> bool:
    return bool(_DEVANAGARI_RE.search(text or ""))


def _split_punct(word: str):
    """'है।' -> ('', 'है', '।')"""
    core = word.strip()
    lead = ""
    while core and core[0] in _EDGE_PUNCT:
        lead, core = lead + core[0], core[1:]
    trail = ""
    while core and core[-1] in _EDGE_PUNCT:
        trail, core = core[-1] + trail, core[:-1]
    return lead, core, trail


def _valid_latin(src: str, out: str) -> bool:
    return bool(out) and not _has_devanagari(out) and len(out) <= 4 * len(src) + 12


def _gemini_transliterate(words: list) -> dict:
    """Ask Gemini for creator-style Hinglish spellings of Devanagari words. Returns {word: latin}."""
    try:
        import config
        if not config.GEMINI_API_KEY:
            return {}
        try:
            from llm import _generate_json
        except ImportError:
            from ..llm import _generate_json
    except Exception:
        return {}

    def _chunk(chunk: list) -> dict:
        prompt = (
            "Transliterate each Hindi (Devanagari) word into casual Hinglish: the Latin-script spelling "
            "Indian YouTubers and Instagram creators use in captions. Examples: है→hai, नहीं→nahi, क्या→kya, "
            "मैं→main, भाई→bhai, अच्छा→accha, कल→kal, मिलते→milte, हैं→hain, यार→yaar, देखो→dekho.\n"
            "If a word is really an ENGLISH word written in Devanagari, use its normal English spelling "
            "(कनेक्टिंग→connecting, गेम→game, सर्वर→server, हेडशॉट→headshot, जंपस्केयर→jumpscare).\n"
            "Never translate meaning. Lowercase. Return ONLY a JSON object mapping every input word to its spelling.\n\n"
            "Words:\n" + json.dumps(chunk, ensure_ascii=False)
        )
        try:
            data = _generate_json(prompt, 60.0)
            return {k: str(v).strip() for k, v in data.items()} if isinstance(data, dict) else {}
        except Exception:
            return {}

    from concurrent.futures import ThreadPoolExecutor
    chunks = [words[i:i + 250] for i in range(0, len(words), 250)]
    out: dict = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for part in pool.map(_chunk, chunks):
            out.update(part)
    return out


def transliterate_words(words: list) -> list:
    """Convert a list of transcript words to Hinglish (Latin script), keeping 1:1 alignment
    so word timestamps stay valid. English words pass through unchanged."""
    cores = []
    for w in words:
        lead, core, trail = _split_punct(w)
        cores.append((lead, core, trail))
    unique = sorted({c for _, c, _ in cores if _has_devanagari(c)})
    mapping = _gemini_transliterate(unique) if unique else {}

    result = []
    for (lead, core, trail), original in zip(cores, words):
        if not _has_devanagari(core):
            result.append(original.strip())
            continue
        latin = mapping.get(core, "")
        if not _valid_latin(core, latin):
            latin = transliterate_to_hinglish(core)
        trail = trail.replace("।", ".").replace("॥", ".")
        lead = lead.replace("।", "").replace("॥", "")
        result.append(f"{lead}{latin}{trail}".strip())
    return result
