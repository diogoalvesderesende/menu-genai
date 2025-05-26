import streamlit as st
import os
import pandas as pd
from PIL import Image
from file_utils import pdf_to_jpeg
from language_utils import categorize_menu_language, language_map
from transcription import process_image_to_excel
from translation import fill_translations

def main():
    # Adicionar espaço no topo e alinhar logo e título
    logo = "logo.png"  
    if os.path.exists(logo):
        col1, col2 = st.columns([0.1, 1])
        with col1:
            st.image(logo, use_container_width='auto')
        with col2:
            st.title("Conversor AI de Menus para Excel com Tradução da Bitte")
    else:
        st.title("Conversor de Menus para Excel com Tradução da Bitte")

    st.markdown("<hr style='border:none; height:1px; background-color:#ccc; margin:20px 0;' />", unsafe_allow_html=True)

    st.write("Carrega o teu menu (PDF ou imagem) e converte-o para um ficheiro Excel estruturado, com traduções em várias línguas.")
    st.write("Pode demorar entre **5 a 10 minutos**, dependendo do tamanho do menu.")
    st.write("Por favor, aguarda pacientemente enquanto o processo decorre.")
    
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
    st.set_page_config(layout="wide")
    # CSS minimalista e elegante, com mais espaçamento no topo
    MAIN_COLOR = "#163c68"
    SECONDARY_COLOR = "#cddff4"
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
    h1 {{
        font-size: 1.25rem !important; /* Decrease title size */
        color: {MAIN_COLOR} !important;
        margin: 0; /* Optional: Remove extra margin */
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
    img.logo {{
        max-height: 50px; /* Matches the title size */
        margin-right: 10px; /* Spacing between logo and title */
    }}
    .header {{
        display: flex;
        align-items: center;
        gap: 10px; /* Adjust spacing between logo and title */
    }}
    </style>
    """, unsafe_allow_html=True)
    main() 