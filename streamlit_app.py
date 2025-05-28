import streamlit as st
from PIL import Image
import os
import numpy as np
import cv2
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from datetime import datetime
import requests
from docx import Document as DocxReader

# Mapeamento diagnóstico → texto de conclusão
DIAGNOSES = {
    'Vaginose Citolítica': 'Conclusão para vaginose citolítica...',
    'Vaginose Bacteriana':  'Conclusão para vaginose bacteriana...',
    'Candidíase':            'Conclusão para candidíase...',
    'Vaginite Aeróbia':      'Conclusão para vaginite aeróbia...',
}

def crop_to_circle_square(pil_img: Image.Image) -> Image.Image:
    cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, dp=1, minDist=gray.shape[0]/8,
        param1=100, param2=30, minRadius=0, maxRadius=0
    )
    if circles is not None:
        x, y, r = np.uint16(np.around(circles[0][0]))
        x1, y1 = max(x-r, 0), max(y-r, 0)
        x2, y2 = min(x+r, cv_img.shape[1]), min(y+r, cv_img.shape[0])
        crop = cv_img[y1:y2, x1:x2]
    else:
        h, w = cv_img.shape[:2]
        side = min(h, w)
        x1, y1 = (w-side)//2, (h-side)//2
        crop = cv_img[y1:y1+side, x1:x1+side]
    return Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))

def download_template(url: str) -> str:
    resp = requests.get(url)
    resp.raise_for_status()
    tmp_path = 'template_temp.docx'
    with open(tmp_path, 'wb') as f:
        f.write(resp.content)
    return tmp_path


def main():
    st.title('🧪 Laudos de Microscopia')

    # Input da URL do template .docx
    template_url = st.text_input('URL de download do template .docx')
    if not template_url:
        st.info('Insira o link de download de um Google Docs no formato .docx.')
        return

    # Upload e preview das imagens originais
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

    # Formulário de dados
    with st.form('form_laudo'):
        name      = st.text_input('Nome Completo da Paciente')
        date_col  = st.date_input('Data da Coleta')
        diagnosis = st.selectbox('Diagnóstico', list(DIAGNOSES.keys()))
        captions  = [st.text_input(f'Legenda {i+1}') for i in range(3)]
        submitted = st.form_submit_button('Gerar Laudo')

    if submitted:
        if not uploaded or len(uploaded) < 3:
            st.error('Por favor, envie 3 imagens antes de gerar o laudo.')
            return

        tpl_path = None
        tmp_imgs = []
        out_docx = None
        try:
            # Baixa o template
            tpl_path = download_template(template_url)

            # Recorta imagens
            cropped = [crop_to_circle_square(Image.open(f)) for f in uploaded[:3]]

            # Renderiza DOCX
            doc = DocxTemplate(tpl_path)
            for i, img in enumerate(cropped, 1):
                img_path = f'tmp_{i}.png'
                img.save(img_path)
                tmp_imgs.append(img_path)

            context = {
                'nome': name,
                'data_coleta': date_col.strftime('%d/%m/%Y'),
                'data_hoje': datetime.now().strftime('%d/%m/%Y'),
                'diagnostico': diagnosis,
                'conclusao_diagnostico': DIAGNOSES.get(diagnosis, ''),
                'legenda1': captions[0],
                'legenda2': captions[1],
                'legenda3': captions[2],
                'imagem1': InlineImage(doc, tmp_imgs[0], width=Mm(50)),
                'imagem2': InlineImage(doc, tmp_imgs[1], width=Mm(50)),
                'imagem3': InlineImage(doc, tmp_imgs[2], width=Mm(50)),
            }
            out_docx = 'laudo_final.docx'
            doc.render(context)
            doc.save(out_docx)

            # Preview do DOCX (texto das seções)
            st.subheader('Preview do Laudo Final (.docx)')
            reader = DocxReader(out_docx)
            preview_text = '\n'.join([p.text for p in reader.paragraphs if p.text.strip()])
            st.text_area('Conteúdo do Laudo', preview_text, height=300)

            # Download do DOCX
            with open(out_docx, 'rb') as f:
                st.download_button('⬇️ Baixar .docx', f.read(), file_name=out_docx)

        except Exception as e:
            st.error(f'Falha ao gerar laudo: {e}')
        finally:
            # Limpeza de arquivos temporários
            paths = ([tpl_path] if tpl_path else []) + tmp_imgs + ([out_docx] if out_docx else [])
            for p in paths:
                if p and os.path.exists(p):
                    os.remove(p)

if __name__ == '__main__':
    main()
