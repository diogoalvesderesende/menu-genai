import streamlit as st
import os
import pandas as pd
import base64
from PIL import Image
import fitz  # PyMuPDF
from openai import OpenAI
import re
import io

# Configuração da página e estilos
st.set_page_config(layout="wide")

MAIN_COLOR = "#163c68"
SECONDARY_COLOR = "#cddff4"

# CSS minimalista e elegante, com mais espaçamento no topo
st.markdown(f"""
<style>
body {{
    background-color: #fff !important;
    font-family: "Helvetica", sans-serif;
    color: #000;
}}
.sidebar .sidebar-content {{
    background-color: #f9f9f9 !important;
    color: #000 !important;
}}
.block-container {{
    background-color: #fff !important;
    padding-top: 40px !important; /* Aumenta o espaçamento no topo */
}}
h1, h2, h3, h4, h5, h6 {{
    color: {MAIN_COLOR} !important;
}}
.st-download-button {{
    background-color: {MAIN_COLOR} !important;
    color: #fff !important;
    border-radius: 4px;
    border: none;
}}
.st-download-button:hover {{
    background-color: #122b4b !important;
    color: #fff !important;
}}
.st-button > button:first-child {{
    background-color: {MAIN_COLOR} !important;
    color: #fff;
    border-radius: 4px;
    border: none;
}}
.st-button > button:first-child:hover {{
    background-color: #122b4b !important;
    color: #fff;
}}
.uploadedFileInfo {{
    color: #555 !important;
}}
</style>
""", unsafe_allow_html=True)

# Set up OpenAI API
api_key = st.secrets["openai_api"]
client = OpenAI(api_key=api_key)
MODEL = "gpt-4o"
MODEL2 = "gpt-4o-mini"

translation_cache = {}

def pdf_to_jpeg(pdf_file):
    pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
    images = []
    for page_number in range(len(pdf_document)):
        page = pdf_document.load_page(page_number)
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    return images

def encode_image_pil(img):
    if img.mode != "RGB":
        img = img.convert("RGB")
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def categorize_menu_language(menu_language):
    prompt = f"""
    Based on the input '{menu_language}', categorize it as one of the following:
    - 'En' for English
    - 'Pt' for Portuguese
    - 'Fr' for French
    - 'De' for German
    - 'Es' for Spanish
    If it doesn't match any, return 'None'.
    Return only the code.
    """
    response = client.chat.completions.create(
        model=MODEL2,
        messages=[
            {"role": "system", "content": "You classify the language."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    return response.choices[0].message.content.strip()

def process_image_to_excel(images, menu_language):
    df = pd.DataFrame(columns=[
        'CategoryTitleDefault', 'SubcategoryTitleDefault', 'ItemNameDefault', 'ItemDescriptionDefault',
        'ItemPrice'
    ])

    system_prompt = f"""
Convert the menu image to a structured table with columns:
- CategoryTitleDefault (Column A) - Category Title
- SubcategoryTitleDefault (Column B) - Subcategory Title (Optional)
- ItemNameDefault (Column C) - Item Name
- ItemDescriptionDefault (Column D) - Item Description (Optional)
- ItemPrice (Column E) - Item Price (just numbers, no currency)

The menu language is {menu_language}.
If multiple languages, only use the {menu_language} portion.

Output in Markdown table format:
| CategoryTitleDefault | SubcategoryTitleDefault | ItemNameDefault | ItemDescriptionDefault | ItemPrice |
    """

    headers_added = False
    for img in images:
        base64_image = encode_image_pil(img)
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",
                 "content": [
                     {"type": "text", "text": "Convert this menu image to a structured Excel sheet format."},
                     {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                 ]
                }
            ],
            temperature=0
        )

        menu_data = response.choices[0].message.content.split('\n')
        for row in menu_data:
            if row.startswith('|') and not row.startswith('|-'):
                columns = [col.strip() for col in row.split('|')[1:-1]]
                if 'CategoryTitleDefault' in columns:
                    if not headers_added:
                        headers_added = True
                    else:
                        continue
                    continue

                if len(columns) == len(df.columns):
                    df.loc[len(df)] = columns

    required_columns = [
        'CategoryTitleDefault', 'SubcategoryTitleDefault', 'ItemNameDefault', 'ItemDescriptionDefault',
        'ItemPrice',
        'CategoryTitleEn', 'SubcategoryTitleEn', 'ItemNameEn', 'ItemDescriptionEn',
        'CategoryTitlePt', 'SubcategoryTitlePt', 'ItemNamePt', 'ItemDescriptionPt',
        'CategoryTitleFr', 'SubcategoryTitleFr', 'ItemNameFr', 'ItemDescriptionFr',
        'CategoryTitleDe', 'SubcategoryTitleDe', 'ItemNameDe', 'ItemDescriptionDe',
        'CategoryTitleEs', 'SubcategoryTitleEs', 'ItemNameEs', 'ItemDescriptionEs'
    ]
    for column in required_columns:
        if column not in df.columns:
            df[column] = ""

    return df

language_map = {
    "Inglês Britânico": "En",
    "Português Europeu": "Pt",
    "Francês Europeu": "Fr",
    "Alemão (Alemanha)": "De",
    "Espanhol Europeu": "Es"
}

def translate_text(text, src_lang_code, tgt_lang_code):
    cache_key = (text, tgt_lang_code)
    if cache_key in translation_cache:
        return translation_cache[cache_key]

    system_prompt = f"You are a translator for a restaurant. Assume the intended meaning is restaurant vocabulary. Translate from {src_lang_code} to {tgt_lang_code}. Return only the translated text."
    user_prompt = f"Translate this text:\n{text}"

    response = client.chat.completions.create(
        model=MODEL2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.0
    )
    translated_text = response.choices[0].message.content.strip()
    translation_cache[cache_key] = translated_text
    return translated_text

def fill_translations(df, menu_language):
    src_code = language_map[menu_language]
    target_langs = [lang for lang in language_map.values() if lang != src_code]

    translation_columns = {
        'CategoryTitleDefault': ['CategoryTitleEn', 'CategoryTitlePt', 'CategoryTitleFr', 'CategoryTitleDe', 'CategoryTitleEs'],
        'SubcategoryTitleDefault': ['SubcategoryTitleEn', 'SubcategoryTitlePt', 'SubcategoryTitleFr', 'SubcategoryTitleDe', 'SubcategoryTitleEs'],
        'ItemNameDefault': ['ItemNameEn', 'ItemNamePt', 'ItemNameFr', 'ItemNameDe', 'ItemNameEs'],
        'ItemDescriptionDefault': ['ItemDescriptionEn', 'ItemDescriptionPt', 'ItemDescriptionFr', 'ItemDescriptionDe', 'ItemDescriptionEs']
    }

    code_to_full = {'En': 'English', 'Pt': 'Portuguese', 'Fr': 'French', 'De': 'German', 'Es': 'Spanish'}

    for index, row in df.iterrows():
        for default_col, target_cols in translation_columns.items():
            if row[default_col] and str(row[default_col]).strip():
                for tgt_col, tgt_code in zip(target_cols, ['En', 'Pt', 'Fr', 'De', 'Es']):
                    if tgt_code != src_code and (pd.isna(row[tgt_col]) or not str(row[tgt_col]).strip()):
                        translated = translate_text(str(row[default_col]), code_to_full[src_code], code_to_full[tgt_code])
                        df.at[index, tgt_col] = translated

def main():
    # Adicionar espaço no topo e alinhar logo e título
    logo = "logo.png"  
    if os.path.exists(logo):
        col1, col2 = st.columns([0.1, 1])
        with col1:
            st.image(logo, use_column_width='auto')
        with col2:
            st.title("Conversor de Menus para Excel com Tradução")
    else:
        st.title("Conversor de Menus para Excel com Tradução")

    st.markdown("<hr style='border:none; height:1px; background-color:#ccc; margin:20px 0;' />", unsafe_allow_html=True)

    st.write("Carrega o teu menu (PDF ou imagem) e converte-o para um ficheiro Excel estruturado, com traduções em várias línguas. Pode demorar entre 5 a 10 minutos, dependendo do tamanho do menu. Por favor, aguarda pacientemente enquanto o processo decorre.")

    uploaded_files = st.file_uploader(
        "Carrega aqui o(s) teu(s) ficheiro(s) (PDF ou imagem):", 
        type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True
    )

    menu_language = st.selectbox(
        "Escolhe a língua do menu:", 
        ["Inglês Britânico", "Português Europeu", "Francês Europeu", "Alemão (Alemanha)", "Espanhol Europeu"]
    )

    output_filename = st.text_input("Nome do ficheiro Excel de saída (sem extensão):")

    if st.button("Converter para Excel"):
        if not uploaded_files:
            st.error("Por favor, carrega pelo menos um ficheiro.")
            return
        if not output_filename:
            st.error("Por favor, indica o nome do ficheiro de saída.")
            return

        language_code = categorize_menu_language(menu_language)
        st.write(f"Código de língua detetado: {language_code}")

        all_images = []
        for uploaded_file in uploaded_files:
            if uploaded_file.type == "application/pdf":
                images = pdf_to_jpeg(uploaded_file)
                all_images.extend(images)
            else:
                img = Image.open(uploaded_file)
                all_images.append(img)

        if all_images:
            with st.spinner("A processar imagens... Pode demorar vários minutos"):
                df = process_image_to_excel(all_images, menu_language)

            with st.spinner("A traduzir o menu... Isto também pode levar algum tempo"):
                fill_translations(df, menu_language)

            output_path = f"{output_filename}.xlsx"
            df.to_excel(output_path, index=False)
            st.success(f"Ficheiro Excel gravado como {output_path}.")

            with open(output_path, "rb") as f:
                st.download_button(
                    label="Descarregar ficheiro Excel",
                    data=f.read(),
                    file_name=output_path,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

if __name__ == "__main__":
    main()
