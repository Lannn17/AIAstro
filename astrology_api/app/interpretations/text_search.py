"""
Text search and astrological interpretations module.
"""
import os
import re
import math
import json
from collections import Counter
from typing import Dict, List, Any, Optional, Tuple
from ..schemas.models import LanguageType

from ..interpretations.translations import translate_astrological_text

# Directory where processed texts are stored
PROCESSED_TEXTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "processed_texts")

# Cache for already-processed documents
DOCUMENT_CACHE = {}
TF_IDF_INDEX = None
DOCUMENT_PARAGRAPHS = {}

def preprocess_text(text: str) -> List[str]:
    """
    Pre-processes text by splitting it into tokens.

    Args:
        text (str): Text to pre-process.

    Returns:
        List[str]: List of tokens.
    """
    # Convert to lowercase
    text = text.lower()

    # Remove special characters and split into tokens
    tokens = re.findall(r'\b\w+\b', text)

    # Remove simple stopwords (articles, prepositions, etc.)
    stopwords = {'o', 'a', 'os', 'as', 'um', 'uma', 'uns', 'umas', 'e', 'de', 'do', 'da', 'dos', 'das', 'em', 'no', 'na', 'nos', 'nas', 'por', 'para', 'com', 'que', 'se', 'the', 'and', 'of', 'to', 'in', 'is', 'for', 'with', 'by', 'on', 'at', 'from', 'an', 'this', 'that', 'these', 'those'}
    tokens = [token for token in tokens if token not in stopwords and len(token) > 1]

    return tokens

def build_tf_idf_index() -> Tuple[Dict[str, Dict[str, float]], Dict[str, List[str]]]:
    """
    Builds a TF-IDF index for processed documents.

    Returns:
        Tuple[Dict[str, Dict[str, float]], Dict[str, List[str]]]:
            TF-IDF index and paragraph dictionary per document.
    """
    global TF_IDF_INDEX, DOCUMENT_PARAGRAPHS

    if TF_IDF_INDEX is not None:
        return TF_IDF_INDEX, DOCUMENT_PARAGRAPHS

    # Check if processed texts directory exists
    if not os.path.exists(PROCESSED_TEXTS_DIR):
        TF_IDF_INDEX = {}
        DOCUMENT_PARAGRAPHS = {}
        return TF_IDF_INDEX, DOCUMENT_PARAGRAPHS

    # Inverted index: term -> document -> frequency
    index = {}
    document_terms = {}
    paragraphs_by_doc = {}

    # Process documents
    doc_count = 0
    for filename in os.listdir(PROCESSED_TEXTS_DIR):
        if not filename.endswith(".txt"):
            continue

        filepath = os.path.join(PROCESSED_TEXTS_DIR, filename)
        doc_id = filename

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

                # Dividir em parágrafos
                paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
                paragraphs_by_doc[doc_id] = paragraphs

                # Process each paragraph as a "sub-document"
                for i, paragraph in enumerate(paragraphs):
                    sub_doc_id = f"{doc_id}:{i}"
                    DOCUMENT_CACHE[sub_doc_id] = paragraph

                    # Pre-process text
                    tokens = preprocess_text(paragraph)

                    # Calculate term frequency
                    term_freq = Counter(tokens)
                    document_terms[sub_doc_id] = term_freq

                    # Update inverted index
                    for term, freq in term_freq.items():
                        if term not in index:
                            index[term] = {}
                        index[term][sub_doc_id] = freq

                doc_count += 1
        except Exception as e:
            print(f"Error processing file {filename}: {str(e)}")

    # Calculate IDF and TF-IDF
    tf_idf_index = {}
    for term, docs in index.items():
        # IDF = log(N / df)
        idf = math.log(doc_count / len(docs))

        for doc_id, freq in docs.items():
            # Normalize TF
            tf = freq / sum(document_terms[doc_id].values())

            # TF-IDF
            tf_idf = tf * idf

            if doc_id not in tf_idf_index:
                tf_idf_index[doc_id] = {}

            tf_idf_index[doc_id][term] = tf_idf

    TF_IDF_INDEX = tf_idf_index
    DOCUMENT_PARAGRAPHS = paragraphs_by_doc

    return tf_idf_index, paragraphs_by_doc

def advanced_text_search(query: str, limit: int = 5, min_score: float = 0.1) -> List[Dict[str, Any]]:
    """
    Performs advanced text search on processed books using TF-IDF.

    Args:
        query (str): Search query.
        limit (int, optional): Maximum number of results. Defaults to 5.
        min_score (float, optional): Minimum score to include a result. Defaults to 0.1.

    Returns:
        List[Dict[str, Any]]: List of search results.
    """
    # Build TF-IDF index (or retrieve from cache)
    tf_idf_index, paragraphs_by_doc = build_tf_idf_index()

    if not tf_idf_index:
        return []

    # Pre-process the query
    query_tokens = preprocess_text(query)

    if not query_tokens:
        return []

    # Score documents
    scores = {}
    for doc_id, terms in tf_idf_index.items():
        score = 0
        for token in query_tokens:
            if token in terms:
                score += terms[token]

        if score > min_score:
            scores[doc_id] = score

    # Sort by score
    sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Prepare results
    results = []
    for doc_id, score in sorted_docs[:limit]:
        # Extract info from doc_id (format: "filename:paragraph_index")
        parts = doc_id.split(":")
        filename = parts[0]
        paragraph_index = int(parts[1])

        # Retrieve paragraph
        paragraph = DOCUMENT_CACHE.get(doc_id, "")

        # Highlight query terms in paragraph
        highlighted = paragraph
        for token in query_tokens:
            pattern = re.compile(r'\b' + re.escape(token) + r'\b', re.IGNORECASE)
            highlighted = pattern.sub(f"**{token.upper()}**", highlighted)

        # Add result
        results.append({
            "source": filename,
            "score": score,
            "paragraph": paragraph,
            "highlighted": highlighted,
            "matched_terms": [token for token in query_tokens if token.lower() in paragraph.lower()]
        })

    return results

def simple_text_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Performs a simple text search on processed books.
    Kept for compatibility; internally uses advanced_text_search.

    Args:
        query (str): Search query.
        limit (int, optional): Maximum number of results. Defaults to 5.

    Returns:
        List[Dict[str, Any]]: List of search results.
    """
    results = advanced_text_search(query, limit)

    # Convert to legacy format
    simple_results = []
    for result in results:
        simple_results.append({
            "source": result["source"],
            "matched_terms": result["matched_terms"],
            "paragraphs": [result["paragraph"]]
        })

    return simple_results

def get_planet_interpretation(planet_name: str, sign: str, house: int, language: LanguageType = "pt") -> Optional[str]:
    """
    Looks up interpretation for a planet in a sign and house.

    Args:
        planet_name (str): Planet name
        sign (str): Sign name
        house (int): House number
        language (LanguageType): Interpretation language. Defaults to "pt".

    Returns:
        Optional[str]: Interpretation found, or None if not found
    """
    # Build query
    query = f"{planet_name} in {sign} in house {house}"

    # Search relevant documents
    results = advanced_text_search(query)
    if not results:
        return None

    # Get most relevant result
    best_match = results[0]

    # Translate if needed
    if language != "en":
        best_match = translate_astrological_text(best_match, language)

    return best_match

def get_sign_interpretation(sign: str, language: str = "pt") -> Optional[Dict[str, Any]]:
    """
    Looks up interpretations for a specific sign.

    Args:
        sign (str): Sign name.
        language (str, optional): Language for text output. Defaults to "pt".

    Returns:
        Optional[Dict[str, Any]]: Interpretation found, or None.
    """
    # Build query
    query = f"signo de {sign} características"
    if language != "pt":
        sign_en = {
            "Áries": "Aries", "Touro": "Taurus", "Gêmeos": "Gemini", "Câncer": "Cancer",
            "Leão": "Leo", "Virgem": "Virgo", "Libra": "Libra", "Escorpião": "Scorpio",
            "Sagitário": "Sagittarius", "Capricórnio": "Capricorn", "Aquário": "Aquarius", "Peixes": "Pisces"
        }.get(sign, sign)

        query = f"{sign_en} sign characteristics"

    # Search
    results = advanced_text_search(query, limit=1)

    if not results:
        return None

    result = results[0]

    # Translate to requested language if needed
    if language != "pt" and language != "en":
        result["paragraph"] = translate_astrological_text(result["paragraph"], "en", language)

    return {
        "source": result["source"],
        "text": result["paragraph"],
        "relevance": result["score"]
    }

def get_house_interpretation(house: int, language: str = "pt") -> Optional[Dict[str, Any]]:
    """
    Looks up interpretations for a specific house.

    Args:
        house (int): House number.
        language (str, optional): Language for text output. Defaults to "pt".

    Returns:
        Optional[Dict[str, Any]]: Interpretation found, or None.
    """
    # Build query
    query = f"casa {house} astrologia"
    if language != "pt":
        query = f"house {house} astrology"

    # Search
    results = advanced_text_search(query, limit=1)

    if not results:
        return None

    result = results[0]

    # Translate to requested language if needed
    if language != "pt" and language != "en":
        result["paragraph"] = translate_astrological_text(result["paragraph"], "en", language)

    return {
        "source": result["source"],
        "text": result["paragraph"],
        "relevance": result["score"]
    }

def get_aspect_interpretation(planet1: str, planet2: str, aspect: str, language: LanguageType = "pt") -> Optional[str]:
    """
    Looks up interpretation for an aspect between two planets.

    Args:
        planet1 (str): First planet name
        planet2 (str): Second planet name
        aspect (str): Aspect name
        language (LanguageType): Interpretation language. Defaults to "pt".

    Returns:
        Optional[str]: Interpretation found, or None if not found
    """
    # Build query
    query = f"{planet1} {aspect} {planet2}"

    # Search relevant documents
    results = advanced_text_search(query)
    if not results:
        return None

    # Get most relevant result
    best_match = results[0]

    # Translate if needed
    if language != "en":
        best_match = translate_astrological_text(best_match, language)

    return best_match

def get_transit_interpretation(transit_planet: str, natal_planet: str, aspect: str, language: str = "pt") -> Optional[Dict[str, Any]]:
    """
    Looks up interpretations for a transit aspect.

    Args:
        transit_planet (str): Transit planet name.
        natal_planet (str): Natal planet name.
        aspect (str): Aspect name.
        language (str, optional): Language for text output. Defaults to "pt".

    Returns:
        Optional[Dict[str, Any]]: Interpretation found, or None.
    """
    # Build query
    query = f"trânsito {transit_planet} {aspect} {natal_planet}"
    if language != "pt":
        # Translate to English
        transit_planet_en = {
            "Sol": "Sun", "Lua": "Moon", "Mercúrio": "Mercury", "Vênus": "Venus",
            "Marte": "Mars", "Júpiter": "Jupiter", "Saturno": "Saturn",
            "Urano": "Uranus", "Netuno": "Neptune", "Plutão": "Pluto",
            "Quíron": "Chiron", "Lilith": "Lilith"
        }.get(transit_planet, transit_planet)

        natal_planet_en = {
            "Sol": "Sun", "Lua": "Moon", "Mercúrio": "Mercury", "Vênus": "Venus",
            "Marte": "Mars", "Júpiter": "Jupiter", "Saturno": "Saturn",
            "Urano": "Uranus", "Netuno": "Neptune", "Plutão": "Pluto",
            "Quíron": "Chiron", "Lilith": "Lilith"
        }.get(natal_planet, natal_planet)

        aspect_en = {
            "Conjunção": "Conjunction", "Oposição": "Opposition",
            "Trígono": "Trine", "Quadratura": "Square", "Sextil": "Sextile"
        }.get(aspect, aspect)

        query = f"transit {transit_planet_en} {aspect_en} {natal_planet_en}"

    # Search
    results = advanced_text_search(query, limit=1)

    if not results:
        return None

    result = results[0]

    # Translate to requested language if needed
    if language != "pt" and language != "en":
        result["paragraph"] = translate_astrological_text(result["paragraph"], "en", language)

    return {
        "source": result["source"],
        "text": result["paragraph"],
        "relevance": result["score"]
    }

def get_natal_chart_interpretations(natal_data: Dict[str, Any], language: str = "pt") -> Dict[str, Any]:
    """
    Gets interpretations for a complete natal chart.

    Args:
        natal_data (Dict[str, Any]): Natal chart data.
        language (str, optional): Language for text output. Defaults to "pt".

    Returns:
        Dict[str, Any]: Natal chart interpretations.
    """
    interpretations = {
        "planets": {},
        "houses": {},
        "aspects": []
    }

    # Planet interpretations
    for planet_key, planet_data in natal_data["planets"].items():
        planet_name = planet_data["name"]
        sign = planet_data["sign"]
        house = planet_data["house"]

        interp = get_planet_interpretation(planet_name, sign, house, language)
        if interp:
            interpretations["planets"][planet_key] = interp

    # House interpretations
    for house_key, house_data in natal_data["houses"].items():
        house_num = int(house_key)

        interp = get_house_interpretation(house_num, language)
        if interp:
            interpretations["houses"][house_key] = interp

    # Aspect interpretations
    for aspect_data in natal_data["aspects"]:
        p1_name = aspect_data["p1_name"]
        p2_name = aspect_data["p2_name"]
        aspect = aspect_data["aspect"]

        interp = get_aspect_interpretation(p1_name, p2_name, aspect, language)
        if interp:
            interpretations["aspects"].append({
                "p1": p1_name,
                "p2": p2_name,
                                "aspect": aspect,
                "interpretation": interp
            })

    return interpretations
