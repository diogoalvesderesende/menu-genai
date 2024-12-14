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

def encode_image(image):
    with open(image, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def categorize_menu_language(menu_language):
    prompt = f"""
    Com base na entrada '{menu_language}', categorize-a como uma das seguintes opções:
    - 'En' para Inglês
    - 'Pt' para Português
    - 'Fr' para Francês
    - 'De' para Alemão
    - 'Es' para Espanhol
    Se o idioma não corresponder a nenhum destes, retorne 'None'.
    Por favor, retorne apenas o código do idioma.
    """

    response = client.chat.completions.create(
        model=MODEL2,
        messages=[
            {"role": "system", "content": "Você é um assistente útil que categoriza entradas de idioma."},
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
    Converta a imagem do menu para um formato estruturado de planilha Excel seguindo o modelo fornecido.
    O idioma do menu é {menu_language}.
    """

    for img in images:
        with st.spinner(f"Processando imagem..."):
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")

            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": {"type": "image_url", "image_url": f"data:image/jpeg;base64,{base64_image}"}}
                ],
                temperature=0
            )

            menu_data = response.choices[0].message.content.split('\n')
            for row in menu_data:
                if row.startswith('|') and not row.startswith('|-'):
                    columns = [col.strip() for col in row.split('|')[1:-1]]
                    if len(columns) == len(df.columns):
                        df.loc[len(df)] = columns

    return df

# Streamlit App
def main():
    st.title("Conversor de Menu para Excel")

    uploaded_files = st.file_uploader(
        "Carregue arquivos PDF ou de imagem", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True
    )

    menu_language = st.selectbox(
        "Selecione o idioma do menu", ["Inglês Britânico", "Português Europeu", "Francês Europeu", "Alemão da Alemanha", "Espanhol Europeu"]
    )

    output_filename = st.text_input("Insira o nome para o arquivo Excel de saída (sem extensão):")

    if st.button("Converter para Excel"):
        if not uploaded_files:
            st.error("Por favor, carregue pelo menos um arquivo.")
        elif not output_filename:
            st.error("Por favor, especifique o nome do arquivo de saída.")
        else:
            language_code = categorize_menu_language(menu_language)
            st.write(f"Código de idioma detectado: {language_code}")

            all_images = []
            for uploaded_file in uploaded_files:
                if uploaded_file.type == "application/pdf":
                    images = pdf_to_jpeg(uploaded_file)
                    all_images.extend(images)
                else:
                    img = Image.open(uploaded_file)
                    all_images.append(img)

            if all_images:
                df = process_image_to_excel(all_images, menu_language)
                output_path = f"{output_filename}.xlsx"
                df.to_excel(output_path, index=False)
                st.success(f"Arquivo Excel salvo como {output_path}.")
                st.download_button(
                    label="Baixar arquivo Excel",
                    data=open(output_path, "rb").read(),
                    file_name=output_path,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

if __name__ == "__main__":
    main()
