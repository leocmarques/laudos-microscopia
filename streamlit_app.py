# app.py

import streamlit as st
import cv2
import numpy as np
from PIL import Image
import io
from docx import Document
from docx.shared import Inches

# 1. Mapeamento diagnóstico → texto de conclusão
DIAGNOSES = {
    'Vaginose Citolítica': 'Conclusão para vaginose citolítica...',
    'Vaginose Bacteriana':  'Conclusão para vaginose bacteriana...',
    'Candidíase':            'Conclusão para candidíase...',
    'Vaginite Aeróbia':      'Conclusão para vaginite aeróbia...',
    # adicione mais conforme necessário
}

def crop_to_circle_square(pil_img: Image.Image) -> Image.Image:
    """Detecta círculo e retorna crop quadrado ao redor; se falhar, faz center crop."""
    cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=gray.shape[0]/8,
        param1=100,
        param2=30,
        minRadius=0,
        maxRadius=0
    )
    if circles is not None:
        x, y, r = np.uint16(np.around(circles[0][0]))
        x1, y1 = max(x-r, 0), max(y-r, 0)
        x2, y2 = min(x+r, cv_img.shape[1]), min(y+r, cv_img.shape[0])
        crop = cv_img[y1:y2, x1:x2]
    else:
        # fallback: square center crop
        h, w = cv_img.shape[:2]
        side = min(h, w)
        x1 = (w - side)//2
        y1 = (h - side)//2
        crop = cv_img[y1:y1+side, x1:x1+side]

    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)

def gerar_laudo(
    name: str,
    date_col,
    diagnosis: str,
    captions: list[str],
    cropped_images: list[Image.Image]
) -> io.BytesIO:
    """Monta um .docx com dados da paciente, conclusão e imagens na segunda página."""
    doc = Document()
    doc.add_heading('Laudo de Microscopia', level=1)
    doc.add_paragraph(f'Nome da Paciente: {name}')
    doc.add_paragraph(f'Data da Coleta: {date_col.strftime("%d/%m/%Y")}')
    doc.add_paragraph(f'Diagnóstico: {diagnosis}')
    doc.add_paragraph('Conclusão:')
    doc.add_paragraph(DIAGNOSES.get(diagnosis, ''))

    doc.add_page_break()
    for img, leg in zip(cropped_images, captions):
        doc.add_paragraph(leg)
        bio = io.BytesIO()
        img.save(bio, format='PNG')
        bio.seek(0)
        doc.add_picture(bio, width=Inches(4))

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

def main():
    st.title('🧪 Laudos de Microscopia')
    with st.form('form_laudo'):
        name = st.text_input('Nome Completo da Paciente')
        date_col = st.date_input('Data da Coleta')
        diagnosis = st.selectbox('Diagnóstico', list(DIAGNOSES.keys()))
        caption1 = st.text_input('Legenda 1')
        caption2 = st.text_input('Legenda 2')
        caption3 = st.text_input('Legenda 3')
        uploaded = st.file_uploader(
            'Envie até 3 fotos (png/jpg)',
            type=['png','jpg','jpeg'],
            accept_multiple_files=True
        )
        submitted = st.form_submit_button('Gerar Laudo')

    if uploaded:
        st.subheader('Pré-via das imagens originais')
        for file in uploaded[:3]:
            img = Image.open(file)
            st.image(img, caption=file.name, use_column_width=True)

    if submitted:
        if len(uploaded) < 3:
            st.error('Por favor, envie 3 imagens.')
            return
        cropped_imgs = [crop_to_circle_square(Image.open(f)) for f in uploaded[:3]]
        st.subheader('Pré-via das imagens recortadas')
        for i, img in enumerate(cropped_imgs, 1):
            st.image(img, caption=f'Imagem {i} recortada', use_column_width=True)

        buffer = gerar_laudo(
            name, date_col, diagnosis,
            [caption1, caption2, caption3],
            cropped_imgs
        )
        st.download_button(
            '⬇️ Baixar Laudo (.docx)',
            data=buffer,
            file_name='laudo.docx',
            mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

    # === FUTURA INTEGRAÇÃO COM GOOGLE SHEETS ===
    # Exemplo: usar gspread/pygsheets, credenciais no st.secrets,
    # abrir planilha modelo, preencher células e salvar.
    # st.write('Integração com Google Sheets ainda não implementada.')

if __name__ == '__main__':
    main()
