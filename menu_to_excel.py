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
    If the language doesn't match any of these, return 'None'.
    Please return only the language code.
    """

    response = client.chat.completions.create(
        model=MODEL2,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that categorizes language input."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    return response.choices[0].message.content.strip()

def translate_with_gpt(text, target_language, menu_language):
    cache_key = (text, target_language)
    if cache_key in translation_cache:
        return translation_cache[cache_key]

    system_prompt = f"""
    You are an expert translator proficient in both {menu_language} and {target_language}.
    Translate all restaurant menu items and descriptions from {menu_language} to {target_language}.

    Guidelines:
    1. Fully translate every term into {target_language}.
    2. Do not retain any original {menu_language} text.
    3. Avoid English defaults in other languages.
    4. Output format:
       {menu_language}: original_text | {target_language}: #%# translated_text #%#
    """
    user_prompt = f"Translate the following text:\n- {menu_language}: #%# {text} #%# | {target_language}: #%#"

    response = client.chat.completions.create(
        model=MODEL2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.0
    )

    translation_match = re.search(r"#%# (.*?) #%#", response.choices[0].message.content)
    if translation_match:
        translated_text = translation_match.group(1).strip()
        translation_cache[cache_key] = translated_text
        return translated_text
    return ""

def fill_translations(df, menu_language):
    language_map = {'En': 'English', 'Pt': 'Portuguese', 'Fr': 'French', 'De': 'German', 'Es': 'Spanish'}
    # Identify the language code from the menu_language input
    code = None
    for k, v in language_map.items():
        if v.lower() in menu_language.lower():
            code = k
            break
    if code is None:
        code = 'None'

    # Define columns for the default language and corresponding target language columns
    translation_columns = {
        'CategoryTitleDefault': ['CategoryTitleEn', 'CategoryTitlePt', 'CategoryTitleFr', 'CategoryTitleDe', 'CategoryTitleEs'],
        'SubcategoryTitleDefault': ['SubcategoryTitleEn', 'SubcategoryTitlePt', 'SubcategoryTitleFr', 'SubcategoryTitleDe', 'SubcategoryTitleEs'],
        'ItemNameDefault': ['ItemNameEn', 'ItemNamePt', 'ItemNameFr', 'ItemNameDe', 'ItemNameEs'],
        'ItemDescriptionDefault': ['ItemDescriptionEn', 'ItemDescriptionPt', 'ItemDescriptionFr', 'ItemDescriptionDe', 'ItemDescriptionEs']
    }

    target_languages = {k: v for k, v in language_map.items() if k != code}

    for attempt in range(3):
        untranslated = False
        for index, row in df.iterrows():
            for default_col, target_cols in translation_columns.items():
                if row[default_col]:
                    for lang_code, target_col in zip(language_map.keys(), target_cols):
                        if lang_code in target_languages and (pd.isna(row[target_col]) or row[target_col].strip() == ''):
                            translation = translate_with_gpt(row[default_col], target_languages[lang_code], menu_language)
                            if translation:
                                df.at[index, target_col] = translation
                            else:
                                untranslated = True
        if not untranslated:
            break

def process_image_to_excel(images, menu_language):
    df = pd.DataFrame(columns=[
        'CategoryTitleDefault', 'SubcategoryTitleDefault', 'ItemNameDefault', 'ItemDescriptionDefault',
        'ItemPrice'
    ])

    system_prompt = f"""
Convert the menu image to a structured Excel sheet format following the provided template and instructions.
The menu's language is {menu_language}.
If the menu has 2 languages, only transcribe what is in {menu_language}.
The template includes columns:
- CategoryTitleDefault
- SubcategoryTitleDefault
- ItemNameDefault
- ItemDescriptionDefault
- ItemPrice

Return the data in a markdown table format (| col1 | col2 | ... |).
    """

    for img in images:
        base64_image = encode_image_pil(img)
        # Sending the image as per the Colab-like approach
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": "Convert this menu image to a structured Excel sheet format."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                ]}
            ],
            temperature=0
        )

        menu_data = response.choices[0].message.content.split('\n')
        for row in menu_data:
            if row.startswith('|') and not row.startswith('|-'):
                columns = [col.strip() for col in row.split('|')[1:-1]]
                if len(columns) == len(df.columns):
                    df.loc[len(df)] = columns

    # Ensure all required columns are present
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

# Global translation cache
translation_cache = {}

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

            # Fill translations
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
