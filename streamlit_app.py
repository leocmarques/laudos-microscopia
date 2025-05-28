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
import requests
import subprocess

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
        h, w = cv_img.shape[:2]
        side = min(h, w)
        x1 = (w - side)//2
        y1 = (h - side)//2
        crop = cv_img[y1:y1+side, x1:x1+side]
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def download_template(url: str) -> str:
    """Baixa o arquivo .docx do URL e retorna caminho local"""
    resp = requests.get(url)
    resp.raise_for_status()
    tmp = 'template_temp.docx'
    with open(tmp, 'wb') as f:
        f.write(resp.content)
    return tmp


def convert_to_pdf(input_path: str) -> str:
    """Converte DOCX em PDF usando LibreOffice em headless mode"""
    output = input_path.replace('.docx', '.pdf')
    try:
        subprocess.run([
            'libreoffice', '--headless', '--convert-to', 'pdf', input_path,
            '--outdir', os.path.dirname(input_path)
        ], check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f'Erro na conversão com LibreOffice: {e}')
    return output


def main():
    st.title('🧪 Laudos de Microscopia')

    # URL do template
    template_url = st.text_input('URL de download do template .docx')
    if not template_url:
        st.info('Insira o link de download de um Google Docs no formato .docx.')
        return

    # upload e preview
    uploaded = st.file_uploader(
        'Envie até 3 fotos (png/jpg)',
        type=['png','jpg','jpeg'],
        accept_multiple_files=True
    )
    if uploaded:
        cols = st.columns(3)
        for idx, col in enumerate(cols):
            col.write(f'Imagem {idx+1}')
            if idx < len(uploaded):
                img = Image.open(uploaded[idx])
                col.image(img, use_container_width=True)

    # formulário
    with st.form('form_laudo'):
        name      = st.text_input('Nome Completo da Paciente')
        date_col  = st.date_input('Data da Coleta')
        diagnosis = st.selectbox('Diagnóstico', list(DIAGNOSES.keys()))
        captions  = [st.text_input(f'Legenda {i+1}') for i in range(3)]
        submitted = st.form_submit_button('Gerar Laudo')

    # submissão
    if submitted:
        if not uploaded or len(uploaded) < 3:
            st.error('Por favor, envie 3 imagens antes de gerar o laudo.')
            return
        try:
            # baixa template
            tpl_path = download_template(template_url)

            # recorte das imagens
            cropped = [crop_to_circle_square(Image.open(f)) for f in uploaded[:3]]

            # renderiza DOCX
            doc = DocxTemplate(tpl_path)
            tmp_imgs = []
            for i, img in enumerate(cropped, 1):
                p = f'tmp_{i}.png'; img.save(p); tmp_imgs.append(p)
            ctx = {
                'nome': name,
                'data_coleta': date_col.strftime('%d/%m/%Y'),
                'data_hoje': datetime.now().strftime('%d/%m/%Y'),
                'diagnostico': diagnosis,
                'conclusao_diagnostico': DIAGNOSES.get(diagnosis,''),
                'legenda1': captions[0],'legenda2': captions[1],'legenda3': captions[2],
                'imagem1': InlineImage(doc, tmp_imgs[0], width=Mm(50)),
                'imagem2': InlineImage(doc, tmp_imgs[1], width=Mm(50)),
                'imagem3': InlineImage(doc, tmp_imgs[2], width=Mm(50)),
            }
            out_docx = 'laudo_final.docx'; doc.render(ctx); doc.save(out_docx)

            # converte para PDF
            out_pdf = convert_to_pdf(out_docx)

            # preview
            st.subheader('Preview do Laudo Final (.pdf)')
            components.iframe(out_pdf, height=600)

            # download
            with open(out_docx,'rb') as f: data_doc = f.read()
            st.download_button('⬇️ Baixar .docx', data_doc, file_name=out_docx)
            with open(out_pdf,'rb') as f: data_pdf = f.read()
            st.download_button('⬇️ Baixar .pdf', data_pdf, file_name=out_pdf)

        except Exception as e:
            st.error(f'Falha ao gerar laudo: {e}')
        finally:
            # limpa arquivos temporários
            for f in [tpl_path] + tmp_imgs + [out_docx, out_pdf]:
                if os.path.exists(f): os.remove(f)

if __name__ == '__main__':
    main()
