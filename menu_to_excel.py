import streamlit as st
import os
import pandas as pd
import base64
from PIL import Image
import fitz  # PyMuPDF
from openai import OpenAI
import re
import io

# Set up OpenAI API
api_key = st.secrets["openai_api"]
client = OpenAI(api_key=api_key)
MODEL = "gpt-4o"
MODEL2 = "gpt-4o-mini"

translation_cache = {}

# Convert PDF to images
def pdf_to_jpeg(pdf_file):
    pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
    images = []
    for page_number in range(len(pdf_document)):
        page = pdf_document.load_page(page_number)
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    return images

# Encode PIL image to base64
def encode_image_pil(img):
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

# Categorize menu language
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

# Convert images to a dataframe by extracting menu data
def process_image_to_excel(images, menu_language):
    df = pd.DataFrame(columns=[
        'CategoryTitleDefault', 'SubcategoryTitleDefault', 'ItemNameDefault', 'ItemDescriptionDefault',
        'ItemPrice'
    ])

    system_prompt = f"""
Convert the menu image to a structured table with columns:
- CategoryTitleDefault
- SubcategoryTitleDefault
- ItemNameDefault
- ItemDescriptionDefault
- ItemPrice

The menu language is {menu_language}.
If the menu has multiple languages, only use the {menu_language} portion.

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
                # Check if this looks like a header row
                if 'CategoryTitleDefault' in columns:
                    # If headers are not yet added, just mark headers_added
                    if not headers_added:
                        headers_added = True
                    else:
                        # Skip if headers encountered again
                        continue
                    continue

                if len(columns) == len(df.columns):
                    df.loc[len(df)] = columns

    # Add translation columns
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

# Map selected language to codes
language_map = {
    "British English": "En",
    "European Portuguese": "Pt",
    "European French": "Fr",
    "German (Germany)": "De",
    "European Spanish": "Es"
}

def translate_text(text, src_lang_code, tgt_lang_code):
    # Check cache
    cache_key = (text, tgt_lang_code)
    if cache_key in translation_cache:
        return translation_cache[cache_key]

    # Simple translation prompt
    system_prompt = f"You are a translator. Translate from {src_lang_code} to {tgt_lang_code}. Return only the translated text."
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
    # Identify source language code
    src_code = language_map[menu_language]
    # Determine other target languages
    target_langs = [lang for lang in language_map.values() if lang != src_code]

    translation_columns = {
        'CategoryTitleDefault': ['CategoryTitleEn', 'CategoryTitlePt', 'CategoryTitleFr', 'CategoryTitleDe', 'CategoryTitleEs'],
        'SubcategoryTitleDefault': ['SubcategoryTitleEn', 'SubcategoryTitlePt', 'SubcategoryTitleFr', 'SubcategoryTitleDe', 'SubcategoryTitleEs'],
        'ItemNameDefault': ['ItemNameEn', 'ItemNamePt', 'ItemNameFr', 'ItemNameDe', 'ItemNameEs'],
        'ItemDescriptionDefault': ['ItemDescriptionEn', 'ItemDescriptionPt', 'ItemDescriptionFr', 'ItemDescriptionDe', 'ItemDescriptionEs']
    }

    # Define language codes more explicitly for translation
    # We'll translate from src_code to each tgt_code individually.
    code_to_full = {'En': 'English', 'Pt': 'Portuguese', 'Fr': 'French', 'De': 'German', 'Es': 'Spanish'}

    for index, row in df.iterrows():
        for default_col, target_cols in translation_columns.items():
            if row[default_col] and str(row[default_col]).strip():
                for tgt_col, tgt_code in zip(target_cols, ['En', 'Pt', 'Fr', 'De', 'Es']):
                    # Only translate if empty and target code is different from source code
                    if tgt_code != src_code and (pd.isna(row[tgt_col]) or not str(row[tgt_col]).strip()):
                        translated = translate_text(str(row[default_col]), code_to_full[src_code], code_to_full[tgt_code])
                        df.at[index, tgt_col] = translated

def main():
    st.title("Menu Converter to Excel with Translation")

    uploaded_files = st.file_uploader(
        "Upload PDF or image files", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True
    )

    menu_language = st.selectbox(
        "Select the menu language", 
        ["British English", "European Portuguese", "European French", "German (Germany)", "European Spanish"]
    )

    output_filename = st.text_input("Enter the output Excel filename (without extension):")

    if st.button("Convert to Excel"):
        if not uploaded_files:
            st.error("Please upload at least one file.")
            return
        if not output_filename:
            st.error("Please provide an output filename.")
            return

        language_code = categorize_menu_language(menu_language)
        st.write(f"Detected language code: {language_code}")

        all_images = []
        for uploaded_file in uploaded_files:
            if uploaded_file.type == "application/pdf":
                images = pdf_to_jpeg(uploaded_file)
                all_images.extend(images)
            else:
                img = Image.open(uploaded_file)
                all_images.append(img)

        if all_images:
            with st.spinner("Processing images..."):
                df = process_image_to_excel(all_images, menu_language)

            with st.spinner("Translating menu items..."):
                fill_translations(df, menu_language)

            output_path = f"{output_filename}.xlsx"
            df.to_excel(output_path, index=False)
            st.success(f"Excel file saved as {output_path}.")

            with open(output_path, "rb") as f:
                st.download_button(
                    label="Download Excel file",
                    data=f.read(),
                    file_name=output_path,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

if __name__ == "__main__":
    main()
