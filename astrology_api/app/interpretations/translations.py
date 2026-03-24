"""
Módulo para traduções astrológicas.

Este módulo fornece funções e constantes para tradução de termos astrológicos.
"""
from typing import Dict, Any, Optional, Literal, List
import re

# Tipo para idiomas suportados
LanguageType = Literal["pt", "en", "es", "fr", "it", "de", "zh", "ja"]

# Mapeamento de planetas
PLANETS_TRANSLATION = {
    "pt": {
        "Sun": "Sol",
        "Moon": "Lua",
        "Mercury": "Mercúrio",
        "Venus": "Vênus",
        "Mars": "Marte",
        "Jupiter": "Júpiter",
        "Saturn": "Saturno",
        "Uranus": "Urano",
        "Neptune": "Netuno",
        "Pluto": "Plutão",
        "Mean_Node": "Nodo Lunar Médio",
        "True_Node": "Nodo Lunar Verdadeiro",
        "Mean_South_Node": "Nodo Sul Médio",
        "True_South_Node": "Nodo Sul Verdadeiro",
        "Chiron": "Quíron",
        "Lilith": "Lilith",
        "Mean_Lilith": "Lilith Média",
        "Ascendant": "Ascendente",
        "Midheaven": "Meio-do-Céu"
    },
    "es": {
        "Sun": "Sol",
        "Moon": "Luna",
        "Mercury": "Mercurio",
        "Venus": "Venus",
        "Mars": "Marte",
        "Jupiter": "Júpiter",
        "Saturn": "Saturno",
        "Uranus": "Urano",
        "Neptune": "Neptuno",
        "Pluto": "Plutón",
        "Mean_Node": "Nodo Lunar Medio",
        "True_Node": "Nodo Lunar Verdadero",
        "Mean_South_Node": "Nodo Sur Medio",
        "True_South_Node": "Nodo Sur Verdadero",
        "Chiron": "Quirón",
        "Lilith": "Lilith",
        "Mean_Lilith": "Lilith Media",
        "Ascendant": "Ascendente",
        "Midheaven": "Medio Cielo"
    },
    "fr": {
        "Sun": "Soleil",
        "Moon": "Lune",
        "Mercury": "Mercure",
        "Venus": "Vénus",
        "Mars": "Mars",
        "Jupiter": "Jupiter",
        "Saturn": "Saturne",
        "Uranus": "Uranus",
        "Neptune": "Neptune",
        "Pluto": "Pluton",
        "Mean_Node": "Nœud Lunaire Moyen",
        "True_Node": "Nœud Lunaire Vrai",
        "Mean_South_Node": "Nœud Sud Moyen",
        "True_South_Node": "Nœud Sud Vrai",
        "Chiron": "Chiron",
        "Lilith": "Lilith",
        "Mean_Lilith": "Lilith Moyenne",
        "Ascendant": "Ascendant",
        "Midheaven": "Milieu du Ciel"
    },
    "it": {
        "Sun": "Sole",
        "Moon": "Luna",
        "Mercury": "Mercurio",
        "Venus": "Venere",
        "Mars": "Marte",
        "Jupiter": "Giove",
        "Saturn": "Saturno",
        "Uranus": "Urano",
        "Neptune": "Nettuno",
        "Pluto": "Plutone",
        "Mean_Node": "Nodo Lunare Medio",
        "True_Node": "Nodo Lunare Vero",
        "Mean_South_Node": "Nodo Sud Medio",
        "True_South_Node": "Nodo Sud Vero",
        "Chiron": "Chirone",
        "Lilith": "Lilith",
        "Mean_Lilith": "Lilith Media",
        "Ascendant": "Ascendente",
        "Midheaven": "Medio Cielo"
    },
    "de": {
        "Sun": "Sonne",
        "Moon": "Mond",
        "Mercury": "Merkur",
        "Venus": "Venus",
        "Mars": "Mars",
        "Jupiter": "Jupiter",
        "Saturn": "Saturn",
        "Uranus": "Uranus",
        "Neptune": "Neptun",
        "Pluto": "Pluto",
        "Mean_Node": "Mittlerer Mondknoten",
        "True_Node": "Wahrer Mondknoten",
        "Mean_South_Node": "Mittlerer Südknoten",
        "True_South_Node": "Wahrer Südknoten",
        "Chiron": "Chiron",
        "Lilith": "Lilith",
        "Mean_Lilith": "Mittlere Lilith",
        "Ascendant": "Aszendent",
        "Midheaven": "Medium Coeli"
    },
    "zh": {
        "Sun": "太阳",
        "Moon": "月亮",
        "Mercury": "水星",
        "Venus": "金星",
        "Mars": "火星",
        "Jupiter": "木星",
        "Saturn": "土星",
        "Uranus": "天王星",
        "Neptune": "海王星",
        "Pluto": "冥王星",
        "Mean_Node": "北交点",
        "True_Node": "北交点",
        "Mean_South_Node": "南交点",
        "True_South_Node": "南交点",
        "Chiron": "凯龙星",
        "Lilith": "黑月莉莉丝",
        "Mean_Lilith": "黑月莉莉丝",
        "Ascendant": "上升点",
        "Midheaven": "天顶"
    },
    "ja": {
        "Sun": "太陽",
        "Moon": "月",
        "Mercury": "水星",
        "Venus": "金星",
        "Mars": "火星",
        "Jupiter": "木星",
        "Saturn": "土星",
        "Uranus": "天王星",
        "Neptune": "海王星",
        "Pluto": "冥王星",
        "Mean_Node": "平均ノースノード",
        "True_Node": "ノースノード",
        "Mean_South_Node": "平均サウスノード",
        "True_South_Node": "サウスノード",
        "Chiron": "カイロン",
        "Lilith": "リリス",
        "Mean_Lilith": "平均リリス",
        "Ascendant": "アセンダント",
        "Midheaven": "MC"
    }
}

# Mapeamento de signos
SIGNS_TRANSLATION = {
    "pt": {
        "Aries": "Áries",
        "Taurus": "Touro",
        "Gemini": "Gêmeos",
        "Cancer": "Câncer",
        "Leo": "Leão",
        "Virgo": "Virgem",
        "Libra": "Libra",
        "Scorpio": "Escorpião",
        "Sagittarius": "Sagitário",
        "Capricorn": "Capricórnio",
        "Aquarius": "Aquário",
        "Pisces": "Peixes"
    },
    "es": {
        "Aries": "Aries",
        "Taurus": "Tauro",
        "Gemini": "Géminis",
        "Cancer": "Cáncer",
        "Leo": "Leo",
        "Virgo": "Virgo",
        "Libra": "Libra",
        "Scorpio": "Escorpio",
        "Sagittarius": "Sagitario",
        "Capricorn": "Capricornio",
        "Aquarius": "Acuario",
        "Pisces": "Piscis"
    },
    "fr": {
        "Aries": "Bélier",
        "Taurus": "Taureau",
        "Gemini": "Gémeaux",
        "Cancer": "Cancer",
        "Leo": "Lion",
        "Virgo": "Vierge",
        "Libra": "Balance",
        "Scorpio": "Scorpion",
        "Sagittarius": "Sagittaire",
        "Capricorn": "Capricorne",
        "Aquarius": "Verseau",
        "Pisces": "Poissons"
    },
    "it": {
        "Aries": "Ariete",
        "Taurus": "Toro",
        "Gemini": "Gemelli",
        "Cancer": "Cancro",
        "Leo": "Leone",
        "Virgo": "Vergine",
        "Libra": "Bilancia",
        "Scorpio": "Scorpione",
        "Sagittarius": "Sagittario",
        "Capricorn": "Capricorno",
        "Aquarius": "Acquario",
        "Pisces": "Pesci"
    },
    "de": {
        "Aries": "Widder",
        "Taurus": "Stier",
        "Gemini": "Zwillinge",
        "Cancer": "Krebs",
        "Leo": "Löwe",
        "Virgo": "Jungfrau",
        "Libra": "Waage",
        "Scorpio": "Skorpion",
        "Sagittarius": "Schütze",
        "Capricorn": "Steinbock",
        "Aquarius": "Wassermann",
        "Pisces": "Fische"
    },
    "zh": {
        "Aries": "白羊座",
        "Taurus": "金牛座",
        "Gemini": "双子座",
        "Cancer": "巨蟹座",
        "Leo": "狮子座",
        "Virgo": "处女座",
        "Libra": "天秤座",
        "Scorpio": "天蝎座",
        "Sagittarius": "射手座",
        "Capricorn": "摩羯座",
        "Aquarius": "水瓶座",
        "Pisces": "双鱼座"
    },
    "ja": {
        "Aries": "牡羊座",
        "Taurus": "牡牛座",
        "Gemini": "双子座",
        "Cancer": "蟹座",
        "Leo": "獅子座",
        "Virgo": "乙女座",
        "Libra": "天秤座",
        "Scorpio": "蠍座",
        "Sagittarius": "射手座",
        "Capricorn": "山羊座",
        "Aquarius": "水瓶座",
        "Pisces": "魚座"
    }
}

# Mapeamento de aspectos
ASPECTS_TRANSLATION = {
    "pt": {
        "Conjunction": "Conjunção",
        "Opposition": "Oposição",
        "Trine": "Trígono",
        "Square": "Quadratura",
        "Sextile": "Sextil",
        "Quincunx": "Quincúncio",
        "Semisextile": "Semisextil",
        "Semisquare": "Semiquadratura",
        "Sesquiquadrate": "Sesquiquadratura",
        "Quintile": "Quintil",
        "Biquintile": "Biquintil"
    },
    "es": {
        "Conjunction": "Conjunción",
        "Opposition": "Oposición",
        "Trine": "Trígono",
        "Square": "Cuadratura",
        "Sextile": "Sextil",
        "Quincunx": "Quincuncio",
        "Semisextile": "Semisextil",
        "Semisquare": "Semicuadratura",
        "Sesquiquadrate": "Sesquicuadratura",
        "Quintile": "Quintil",
        "Biquintile": "Biquintil"
    },
    "fr": {
        "Conjunction": "Conjonction",
        "Opposition": "Opposition",
        "Trine": "Trigone",
        "Square": "Carré",
        "Sextile": "Sextile",
        "Quincunx": "Quinconce",
        "Semisextile": "Demi-sextile",
        "Semisquare": "Demi-carré",
        "Sesquiquadrate": "Sesqui-carré",
        "Quintile": "Quintile",
        "Biquintile": "Bi-quintile"
    },
    "it": {
        "Conjunction": "Congiunzione",
        "Opposition": "Opposizione",
        "Trine": "Trigono",
        "Square": "Quadratura",
        "Sextile": "Sestile",
        "Quincunx": "Quinconce",
        "Semisextile": "Semisestile",
        "Semisquare": "Semiquadratura",
        "Sesquiquadrate": "Sesquiquadratura",
        "Quintile": "Quintile",
        "Biquintile": "Biquintile"
    },
    "de": {
        "Conjunction": "Konjunktion",
        "Opposition": "Opposition",
        "Trine": "Trigon",
        "Square": "Quadrat",
        "Sextile": "Sextil",
        "Quincunx": "Quincunx",
        "Semisextile": "Halbsextil",
        "Semisquare": "Halbquadrat",
        "Sesquiquadrate": "Anderthalbquadrat",
        "Quintile": "Quintil",
        "Biquintile": "Biquintil"
    },
    "zh": {
        "Conjunction": "合相",
        "Opposition": "对冲",
        "Trine": "三分相",
        "Square": "四分相",
        "Sextile": "六分相",
        "Quincunx": "十二分之五相",
        "Semisextile": "半六分相",
        "Semisquare": "半四分相",
        "Sesquiquadrate": "倍半四分相",
        "Quintile": "五分相",
        "Biquintile": "双五分相"
    },
    "ja": {
        "Conjunction": "コンジャンクション",
        "Opposition": "オポジション",
        "Trine": "トライン",
        "Square": "スクエア",
        "Sextile": "セクスタイル",
        "Quincunx": "クインカンクス",
        "Semisextile": "セミセクスタイル",
        "Semisquare": "セミスクエア",
        "Sesquiquadrate": "セスキクアドレート",
        "Quintile": "クインタイル",
        "Biquintile": "バイクインタイル"
    }
}

# Mapeamento de casas
HOUSES_TRANSLATION = {
    "pt": {
        "1": "Primeira Casa",
        "2": "Segunda Casa",
        "3": "Terceira Casa",
        "4": "Quarta Casa",
        "5": "Quinta Casa",
        "6": "Sexta Casa",
        "7": "Sétima Casa",
        "8": "Oitava Casa",
        "9": "Nona Casa",
        "10": "Décima Casa",
        "11": "Décima Primeira Casa",
        "12": "Décima Segunda Casa"
    },
    "es": {
        "1": "Primera Casa",
        "2": "Segunda Casa",
        "3": "Tercera Casa",
        "4": "Cuarta Casa",
        "5": "Quinta Casa",
        "6": "Sexta Casa",
        "7": "Séptima Casa",
        "8": "Octava Casa",
        "9": "Novena Casa",
        "10": "Décima Casa",
        "11": "Undécima Casa",
        "12": "Duodécima Casa"
    },
    "fr": {
        "1": "Première Maison",
        "2": "Deuxième Maison",
        "3": "Troisième Maison",
        "4": "Quatrième Maison",
        "5": "Cinquième Maison",
        "6": "Sixième Maison",
        "7": "Septième Maison",
        "8": "Huitième Maison",
        "9": "Neuvième Maison",
        "10": "Dixième Maison",
        "11": "Onzième Maison",
        "12": "Douzième Maison"
    },
    "it": {
        "1": "Prima Casa",
        "2": "Seconda Casa",
        "3": "Terza Casa",
        "4": "Quarta Casa",
        "5": "Quinta Casa",
        "6": "Sesta Casa",
        "7": "Settima Casa",
        "8": "Ottava Casa",
        "9": "Nona Casa",
        "10": "Decima Casa",
        "11": "Undicesima Casa",
        "12": "Dodicesima Casa"
    },
    "de": {
        "1": "Erstes Haus",
        "2": "Zweites Haus",
        "3": "Drittes Haus",
        "4": "Viertes Haus",
        "5": "Fünftes Haus",
        "6": "Sechstes Haus",
        "7": "Siebtes Haus",
        "8": "Achtes Haus",
        "9": "Neuntes Haus",
        "10": "Zehntes Haus",
        "11": "Elftes Haus",
        "12": "Zwölftes Haus"
    },
    "zh": {
        "1": "第一宫", "2": "第二宫", "3": "第三宫", "4": "第四宫",
        "5": "第五宫", "6": "第六宫", "7": "第七宫", "8": "第八宫",
        "9": "第九宫", "10": "第十宫", "11": "第十一宫", "12": "第十二宫"
    },
    "ja": {
        "1": "第1ハウス", "2": "第2ハウス", "3": "第3ハウス", "4": "第4ハウス",
        "5": "第5ハウス", "6": "第6ハウス", "7": "第7ハウス", "8": "第8ハウス",
        "9": "第9ハウス", "10": "第10ハウス", "11": "第11ハウス", "12": "第12ハウス"
    }
}

def translate_planet(planet_name: str, language: LanguageType) -> str:
    """
    Traduz o nome de um planeta para o idioma especificado.
    
    Args:
        planet_name (str): Nome do planeta em inglês.
        language (LanguageType): Idioma para tradução.
        
    Returns:
        str: Nome do planeta traduzido ou o nome original se não houver tradução.
    """
    if language == "en":
        return planet_name
    
    return PLANETS_TRANSLATION.get(language, {}).get(planet_name, planet_name)

def translate_sign(sign_name: str, language: LanguageType) -> str:
    """
    Traduz o nome de um signo para o idioma especificado.
    
    Args:
        sign_name (str): Nome do signo em inglês.
        language (LanguageType): Idioma para tradução.
        
    Returns:
        str: Nome do signo traduzido ou o nome original se não houver tradução.
    """
    if language == "en":
        return sign_name
    
    return SIGNS_TRANSLATION.get(language, {}).get(sign_name, sign_name)

def translate_aspect(aspect_name: str, language: LanguageType) -> str:
    """
    Traduz o nome de um aspecto para o idioma especificado.
    
    Args:
        aspect_name (str): Nome do aspecto em inglês.
        language (LanguageType): Idioma para tradução.
        
    Returns:
        str: Nome do aspecto traduzido ou o nome original se não houver tradução.
    """
    if language == "en":
        return aspect_name
    
    return ASPECTS_TRANSLATION.get(language, {}).get(aspect_name, aspect_name)

def translate_house(house_number: str, language: LanguageType) -> str:
    """
    Traduz o nome de uma casa para o idioma especificado.
    
    Args:
        house_number (str): Número da casa como string.
        language (LanguageType): Idioma para tradução.
        
    Returns:
        str: Nome da casa traduzido ou o número original se não houver tradução.
    """
    if language == "en":
        return f"House {house_number}"
    
    return HOUSES_TRANSLATION.get(language, {}).get(house_number, f"House {house_number}")

def get_all_translation_terms(language: LanguageType) -> Dict[str, str]:
    """
    Obtém todos os termos de tradução para um idioma específico.
    
    Args:
        language (LanguageType): Idioma para obter os termos.
        
    Returns:
        Dict[str, str]: Dicionário com todos os termos de tradução.
    """
    if language == "en":
        return {}  # Não há tradução para inglês
    
    translations = {}
    
    # Adicionar planetas
    for planet_en, planet_translated in PLANETS_TRANSLATION.get(language, {}).items():
        translations[planet_en] = planet_translated
    
    # Adicionar signos
    for sign_en, sign_translated in SIGNS_TRANSLATION.get(language, {}).items():
        translations[sign_en] = sign_translated
    
    # Adicionar aspectos
    for aspect_en, aspect_translated in ASPECTS_TRANSLATION.get(language, {}).items():
        translations[aspect_en] = aspect_translated
    
    # Adicionar casas
    for house_num, house_translated in HOUSES_TRANSLATION.get(language, {}).items():
        translations[f"House {house_num}"] = house_translated
    
    return translations

def translate_astrological_text(text: str, target_language: LanguageType, source_language: LanguageType = "en") -> str:
    """
    Traduz um texto astrológico do idioma fonte para o idioma alvo.
    
    Args:
        text (str): Texto a ser traduzido
        target_language (LanguageType): Idioma alvo
        source_language (LanguageType, optional): Idioma fonte. Defaults to "en".
    
    Returns:
        str: Texto traduzido
    """
    if target_language == source_language:
        return text
        
    # Traduzir planetas
    for en_name, trans_name in PLANETS_TRANSLATION.get(target_language, {}).items():
        text = re.sub(fr"\b{en_name}\b", trans_name, text, flags=re.IGNORECASE)
        
    # Traduzir signos
    for en_name, trans_name in SIGNS_TRANSLATION.get(target_language, {}).items():
        text = re.sub(fr"\b{en_name}\b", trans_name, text, flags=re.IGNORECASE)
        
    # Traduzir aspectos
    for en_name, trans_name in ASPECTS_TRANSLATION.get(target_language, {}).items():
        text = re.sub(fr"\b{en_name}\b", trans_name, text, flags=re.IGNORECASE)
        
    # Traduzir casas
    for num, trans_name in HOUSES_TRANSLATION.get(target_language, {}).items():
        text = re.sub(fr"\bHouse {num}\b", trans_name, text, flags=re.IGNORECASE)
        
    return text

def get_supported_languages() -> List[Dict[str, str]]:
    """
    Retorna a lista de idiomas suportados.
    
    Returns:
        List[Dict[str, str]]: Lista de idiomas suportados com códigos e nomes.
    """
    return [
        {"code": "zh", "name": "中文"},
        {"code": "ja", "name": "日本語"},
        {"code": "en", "name": "English"},
        {"code": "pt", "name": "Português"},
        {"code": "es", "name": "Español"},
        {"code": "fr", "name": "Français"},
        {"code": "it", "name": "Italiano"},
        {"code": "de", "name": "Deutsch"}
    ]
