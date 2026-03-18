"""
Módulo para geração de gráficos SVG astrológicos.

Este módulo contém funções auxiliares para geração de gráficos SVG
utilizando a biblioteca Kerykeion.
"""
from kerykeion import KerykeionChartSVG, AstrologicalSubject
import os
import tempfile
from typing import Optional, Dict, Any, Tuple

def generate_svg_chart(
    natal_subject: AstrologicalSubject,
    transit_subject: Optional[AstrologicalSubject] = None,
    chart_type: str = "Natal",
    show_aspects: bool = True,
    theme: str = "light",
    language: str = "pt"
) -> str:
    """
    Gera um gráfico astrológico em formato SVG.
    
    Args:
        natal_subject (AstrologicalSubject): Objeto AstrologicalSubject para o mapa natal.
        transit_subject (Optional[AstrologicalSubject], opcional): Objeto AstrologicalSubject para o mapa de trânsito.
        chart_type (str, opcional): Tipo de gráfico ("Natal", "Transit", "Combined"). Padrão é "Natal".
        show_aspects (bool, opcional): Se deve mostrar linhas de aspectos. Padrão é True.
        theme (str, opcional): Tema de cores ("light", "dark"). Padrão é "light".
        language (str, opcional): Idioma para os textos ("pt", "en"). Padrão é "pt".
        
    Returns:
        str: Conteúdo SVG do gráfico gerado.
        
    Raises:
        Exception: Se ocorrer um erro durante a geração do gráfico.
    """
    try:
        # Kerykeion 4.x theme mapping
        kery_theme = "dark" if theme == "dark" else "light"
        # Kerykeion 4.x chart_language is uppercase 2-letter code
        lang_map = {"pt": "PT", "en": "EN", "es": "ES", "fr": "FR", "it": "IT", "de": "DE"}
        kery_lang = lang_map.get(language, "EN")

        with tempfile.TemporaryDirectory() as temp_dir:
            chart_svg_generator = KerykeionChartSVG(
                natal_subject,
                chart_type=chart_type,
                second_obj=transit_subject,
                new_output_directory=temp_dir,
                theme=kery_theme,
                chart_language=kery_lang
            )
            chart_svg_generator.makeSVG()

            # Kerykeion names the file "{name} - {chart_type} Chart.svg"
            svg_files = [f for f in os.listdir(temp_dir) if f.endswith(".svg")]
            if not svg_files:
                raise Exception("Arquivo SVG não encontrado após geração")

            with open(os.path.join(temp_dir, svg_files[0]), 'r', encoding='utf-8') as f:
                return f.read()

    except Exception as e:
        raise Exception(f"Erro ao gerar gráfico SVG: {str(e)}")

def customize_svg(svg_content: str, options: Dict[str, Any]) -> str:
    """
    Personaliza um gráfico SVG com base nas opções fornecidas.
    
    Args:
        svg_content (str): Conteúdo SVG original.
        options (Dict[str, Any]): Opções de personalização.
        
    Returns:
        str: Conteúdo SVG personalizado.
    """
    # Implementar lógica de personalização do SVG
    # Por exemplo, alterar cores, fontes, etc.
    
    # Por enquanto, apenas retornamos o SVG original
    return svg_content

def get_chart_dimensions(chart_size: str = "medium") -> Tuple[int, int]:
    """
    Obtém as dimensões do gráfico com base no tamanho especificado.
    
    Args:
        chart_size (str, opcional): Tamanho do gráfico ("small", "medium", "large"). Padrão é "medium".
        
    Returns:
        Tuple[int, int]: Dimensões do gráfico (largura, altura).
    """
    sizes = {
        "small": (600, 600),
        "medium": (800, 800),
        "large": (1000, 1000),
        "xlarge": (1200, 1200)
    }
    
    return sizes.get(chart_size, (800, 800))
