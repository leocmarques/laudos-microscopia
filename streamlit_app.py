import streamlit as st
from PIL import Image
import os
import numpy as np
import cv2
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from datetime import datetime
from zoneinfo import ZoneInfo
import requests

# --- (DIAGNOSES, resize_image, crop_to_circle_square, download_template permanecem iguais) ---

def main():
    st.title('🧪 Laudos de Microscopia')
    today_sp = datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y')

    # ID do template no Google Docs
    file_id = st.text_input(
        'ID do arquivo Google Docs para template (.docx)',
        value='1qppBMNjSTlUMtXMQ7EtHt2fDHpnwnQjMqNPl7b3A4oUa'
    )
    if not file_id:
        st.info('Insira o ID do arquivo no Google Docs.')
        return
    template_url = (
        'https://docs.google.com/feeds/download/documents/export/'
        f'Export?id={file_id}&exportFormat=docx'
    )

    # Pré-configura listas para imagens e legendas
    images = [None, None, None]
    legend_inputs = ["", "", ""]

    st.subheader("Selecione a fonte e a imagem para cada foto")
    cols = st.columns(3)
    for i, col in enumerate(cols):
        col.markdown(f"**Foto {i+1}**")
        source = col.selectbox(
            "Fonte:", 
            ("Upload", "Webcam"),
            key=f"source_{i}"
        )

        if source == "Upload":
            img_file = col.file_uploader(
                "Escolha um arquivo",
                type=['png','jpg','jpeg'],
                key=f"upload_{i}",
                accept_multiple_files=False
            )
        else:
            img_file = col.camera_input(
                f"Capturar foto {i+1}",
                key=f"camera_{i}"
            )

        if img_file is not None:
            # abre e redimensiona para preview
            pil_img = Image.open(img_file)
            pil_img = resize_image(pil_img)
            col.image(pil_img, use_column_width=True)
            images[i] = img_file
            legend_inputs[i] = col.text_input(
                f"Legenda {i+1}",
                key=f"legend_{i}"
            )

    # Formulário: dados da paciente e diagnóstico
    with st.form('form_laudo'):
        name = st.text_input('Nome Completo da Paciente')
        date_col = st.date_input('Data da Coleta')
        diagnosis = st.selectbox('Diagnóstico', list(DIAGNOSES.keys()))
        submitted = st.form_submit_button('Gerar Laudo')

    if submitted:
        # Validação: todas as 3 imagens
        if any(img is None for img in images):
            st.error('Por favor, forneça 3 imagens antes de gerar o laudo.')
            return

        try:
            # Download do template
            tpl_path = download_template(template_url)

            # Processa cortes circulares
            cropped_imgs = []
            for img_file in images:
                img = Image.open(img_file)
                cropped = crop_to_circle_square(img)
                cropped_imgs.append(cropped)

            # Define autores e referências conforme diagnóstico
            if diagnosis.startswith('Vaginose Citolítica'):
                autores = 'Cibley & Cibley (1991)'
                referencia = (
                    'Cibley LJ, Cibley LJ. Cytolytic vaginosis. '
                    'American Journal of Obstetrics and Gynecology 1991; 165:1245-1248.'
                )
            elif diagnosis == 'Vaginite Aeróbia':
                autores = 'Donders et al. (2002)'
                referencia = (
                    'Donders GGG, Vereecken A, Bosmans E, Dekeersmaecker A, '
                    'Salembier G, Spitz B. Aerobic vaginitis. BJOG 2002;109:34-43.'
                )
            else:
                autores = 'Nugent et al. (1991)'
                referencia = (
                    'Nugent RP, Krohn MA, Hillier SL. Reliability of diagnosing BV '
                    'improved by standardized Gram stain. J Clin Microbiol 1991;29:297-301.'
                )

            # Renderiza no DOCX
            doc = DocxTemplate(tpl_path)
            tmp_imgs = []
            for idx, pil_img in enumerate(cropped_imgs, start=1):
                tmp_path = f"tmp_img_{idx}.png"
                pil_img.save(tmp_path)
                tmp_imgs.append(tmp_path)

            context = {
                'nome': name,
                'data_coleta': date_col.strftime('%d/%m/%Y'),
                'data_hoje': today_sp,
                'diagnostico': diagnosis,
                'conclusao_diagnostico': DIAGNOSES[diagnosis],
                'autores': autores,
                'referencia_completa': referencia,
                'legenda1': legend_inputs[0],
                'legenda2': legend_inputs[1],
                'legenda3': legend_inputs[2],
                'imagem1': InlineImage(doc, tmp_imgs[0], width=Mm(50)),
                'imagem2': InlineImage(doc, tmp_imgs[1], width=Mm(50)),
                'imagem3': InlineImage(doc, tmp_imgs[2], width=Mm(50)),
            }
            doc.render(context)

            out_docx = f"Laudo - {name.strip().replace(' ', '_')}.docx"
            doc.save(out_docx)

            # Botão de download
            with open(out_docx, "rb") as f:
                st.download_button(
                    "⬇️ Baixar Laudo (.docx)",
                    data=f.read(),
                    file_name=out_docx
                )

        except Exception as e:
            st.error(f"Erro ao gerar laudo: {e}")

        finally:
            # Limpa temporários
            for p in tmp_imgs + ([tpl_path] if tpl_path else []) + ([out_docx] if 'out_docx' in locals() else []):
                if p and os.path.exists(p):
                    os.remove(p)

if __name__ == "__main__":
    main()
