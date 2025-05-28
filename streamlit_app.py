import streamlit as st
from PIL import Image
import io
import os
import numpy as np
import cv2
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from datetime import datetime
import streamlit.components.v1 as components
# Para gerar PDF, instale: pip install docx2pdf
from docx2pdf import convert

# 1. Mapeamento diagnóstico → texto de conclusão
DIAGNOSES = {
    'Vaginose Citolítica': 'Conclusão para vaginose citolítica...',
    'Vaginose Bacteriana':  'Conclusão para vaginose bacteriana...',
    'Candidíase':            'Conclusão para candidíase...',
    'Vaginite Aeróbia':      'Conclusão para vaginite aeróbia...',
    # adicione mais conforme necessário
}

TEMPLATE_PATH = 'template.docx'


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
        h, w = cv_img.shape[:2]
        side = min(h, w)
        x1 = (w - side)//2
        y1 = (h - side)//2
        crop = cv_img[y1:y1+side, x1:x1+side]
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def main():
    st.title('🧪 Laudos de Microscopia')

    # 1) Uploader e preview das originais
    uploaded = st.file_uploader(
        'Envie até 3 fotos (png/jpg)',
        type=['png','jpg','jpeg'],
        accept_multiple_files=True
    )
    if uploaded:
        st.subheader('Pré-visualização das imagens originais')
        cols = st.columns(3)
        for idx, col in enumerate(cols):
            col.write(f'Imagem {idx+1}')
            if idx < len(uploaded):
                img = Image.open(uploaded[idx])
                col.image(img, use_container_width=True)

    # 2) Formulário de dados
    with st.form('form_laudo'):
        name      = st.text_input('Nome Completo da Paciente')
        date_col  = st.date_input('Data da Coleta')
        diagnosis = st.selectbox('Diagnóstico', list(DIAGNOSES.keys()))
        captions  = [st.text_input(f'Legenda {i+1}') for i in range(3)]
        submitted = st.form_submit_button('Gerar Laudo')

    # 3) Ao submeter, recorta, gera DOCX e PDF, exibe preview e downloads
    if submitted:
        if not uploaded or len(uploaded) < 3:
            st.error('Por favor, envie 3 imagens antes de gerar o laudo.')
            return

        # recorte das imagens
        cropped_imgs = [crop_to_circle_square(Image.open(f)) for f in uploaded[:3]]

        # carrega template e salva imagens temporárias
        doc = DocxTemplate(TEMPLATE_PATH)
        tmp_files = []
        for i, img in enumerate(cropped_imgs, 1):
            tmp_path = f'tmp_img_{i}.png'
            img.save(tmp_path)
            tmp_files.append(tmp_path)

        # prepara contexto incluindo novas variáveis
        context = {
            'nome': name,
            'data_coleta': date_col.strftime('%d/%m/%Y'),
            'data_hoje': datetime.now().strftime('%d/%m/%Y'),
            'diagnostico': diagnosis,
            'conclusao_diagnostico': DIAGNOSES.get(diagnosis, ''),
            'legenda1': captions[0],
            'legenda2': captions[1],
            'legenda3': captions[2],
            'imagem1': InlineImage(doc, tmp_files[0], width=Mm(50)),
            'imagem2': InlineImage(doc, tmp_files[1], width=Mm(50)),
            'imagem3': InlineImage(doc, tmp_files[2], width=Mm(50)),
        }
        # renderiza e salva DOCX
        out_docx = 'laudo_final.docx'
        doc.render(context)
        doc.save(out_docx)

        # converte para PDF
        out_pdf = out_docx.replace('.docx', '.pdf')
        try:
            convert(out_docx, out_pdf)
        except Exception as e:
            st.warning(f'Erro ao gerar PDF: {e}')

        # remove temporários
        for p in tmp_files:
            os.remove(p)

        # preview do PDF
        st.subheader('Preview do Laudo Final')
        if os.path.exists(out_pdf):
            components.iframe(out_pdf, height=600)
        else:
            st.info('Preview em PDF não disponível.')

        # botões de download
        with open(out_docx, 'rb') as f:
            docx_data = f.read()
        st.download_button(
            '⬇️ Baixar .docx', data=docx_data,
            file_name=out_docx,
            mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        if os.path.exists(out_pdf):
            with open(out_pdf, 'rb') as f:
                pdf_data = f.read()
            st.download_button(
                '⬇️ Baixar .pdf', data=pdf_data,
                file_name=out_pdf,
                mime='application/pdf'
            )

if __name__ == '__main__':
    main()
