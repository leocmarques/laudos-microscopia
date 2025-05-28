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

# Novo mapeamento diagnóstico → texto de conclusão
DIAGNOSES = {
    'Vaginose Citolítica': 'O padrão de microbiota apresentado na lâmina pesquisada é de Vaginose citolítica.',
    'Vaginose Citolítica + candidíase': (
        'O padrão de microbiota apresentado na lâmina pesquisada é de Vaginose citolítica. '
        'Observa-se concomitantemente presença de elementos micóticos.'
    ),
    'Vaginose Bacteriana escore 7': (
        'O padrão de microbiota apresentado na lâmina pesquisada é de Vaginose Bacteriana (escore 7).'
    ),
    'Vaginose Bacteriana escore 7 + candidíase': (
        'O padrão de microbiota apresentado na lâmina pesquisada é de Vaginose Bacteriana (escore 7). '
        'Observa-se concomitantemente presença de elementos micóticos.'
    ),
    'Vaginose Bacteriana escore 8': (
        'O padrão de microbiota apresentado na lâmina pesquisada é de Vaginose Bacteriana (escore 8).'
    ),
    'Vaginose Bacteriana escore 8 + candidíase': (
        'O padrão de microbiota apresentado na lâmina pesquisada é de Vaginose Bacteriana (escore 8). '
        'Observa-se concomitantemente presença de elementos micóticos.'
    ),
    'Vaginose Bacteriana escore 10': (
        'O padrão de microbiota apresentado na lâmina pesquisada é de Vaginose Bacteriana (escore 10). '
        'Observa-se ausência de Lactobacillus e muitas bactérias do core patológico da Vaginose Bacteriana.'
    ),
    'Vaginose Bacteriana escore 10 + candidíase': (
        'O padrão de microbiota apresentado na lâmina pesquisada é de Vaginose Bacteriana (escore 10). '
        'Observa-se ausência de Lactobacillus e muitas bactérias do core patológico da Vaginose Bacteriana. '
        'Observa-se concomitantemente presença de elementos micóticos.'
    ),
    'Candidíase': (
        'Observa-se presença de elementos micóticos (pseudo-hifas, blastoconídios e leveduras).'
    ),
    'Vaginite Aeróbia': 'O padrão de microbiota apresentado na lâmina pesquisada é de Vaginite aeróbia.',
    'Flora I': 'O padrão de microbiota apresentado na lâmina pesquisada é de Flora I (escore 1).',
    'Flora II': (
        'O padrão de microbiota apresentado na lâmina pesquisada é de Flora II. '
        'Concomitantemente visualiza-se a presença de inúmeros polimorfonucleares (3+/4+).'
    ),
    'Flora III - Vaginose bacteriana': 'O padrão de microbiota apresentado na lâmina pesquisada é de Flora III.',
}

# Redimensiona imagem para que o maior lado seja, no máximo, max_dim pixels
def resize_image(pil_img: Image.Image, max_dim: int = 800) -> Image.Image:
    w, h = pil_img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        new_size = (int(w * scale), int(h * scale))
        return pil_img.resize(new_size, Image.LANCZOS)
    return pil_img

# Recorta a imagem ao redor do círculo detectado; se não detectar, faz center crop quadrado
def crop_to_circle_square(pil_img: Image.Image) -> Image.Image:
    cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, dp=1, minDist=gray.shape[0] / 8,
        param1=100, param2=30
    )
    if circles is not None:
        x, y, r = np.uint16(np.around(circles[0][0]))
        x1, y1 = max(x - r, 0), max(y - r, 0)
        x2, y2 = min(x + r, cv_img.shape[1]), min(y + r, cv_img.shape[0])
        crop = cv_img[y1:y2, x1:x2]
    else:
        h, w = cv_img.shape[:2]
        side = min(h, w)
        x1, y1 = (w - side) // 2, (h - side) // 2
        crop = cv_img[y1:y1 + side, x1:x1 + side]
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)

# Baixa template DOCX a partir de URL
def download_template(url: str) -> str:
    resp = requests.get(url)
    resp.raise_for_status()
    tmp_path = 'template_temp.docx'
    with open(tmp_path, 'wb') as f:
        f.write(resp.content)
    return tmp_path

# Função principal
def main():
    st.title('🧪 Laudos de Microscopia')
    today_sp = datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y')
    # ID do Google Docs
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
    # Upload e legendas
    uploaded = st.file_uploader(
        'Envie até 3 fotos (png/jpg)',
        type=['png', 'jpg', 'jpeg'],
        accept_multiple_files=True
    )
    legend_inputs = ['', '', '']
    if uploaded:
        st.subheader('Pré-visualização e legendas')
        cols = st.columns(3)
        for idx, col in enumerate(cols):
            col.write(f'Imagem {idx + 1}')
            if idx < len(uploaded):
                img = Image.open(uploaded[idx])
                img = resize_image(img)
                col.image(img, use_container_width=True)
            legend_inputs[idx] = col.text_input(f'Legenda {idx + 1}')
    # Formulário
    with st.form('form_laudo'):
        name = st.text_input('Nome Completo da Paciente')
        date_col = st.date_input('Data da Coleta')
        diagnosis = st.selectbox('Diagnóstico', list(DIAGNOSES.keys()))
        submitted = st.form_submit_button('Gerar Laudo')
    if submitted:
        if not uploaded or len(uploaded) < 3:
            st.error('Por favor, envie 3 imagens antes de gerar o laudo.')
            return
        tpl_path = None
        tmp_imgs = []
        out_docx = None
        try:
            tpl_path = download_template(template_url)
            cropped_imgs = []
            for f in uploaded[:3]:
                img = Image.open(f)
                img = resize_image(img)
                cropped = crop_to_circle_square(img)
                cropped_imgs.append(cropped)
            # Define autores e referência
            if diagnosis in ['Vaginose Citolítica', 'Vaginose Citolítica + candidíase']:
                autores = 'Cibley & Cibley (1991)'
                referencia = (
                    'Cibley LJ, Cibley LJ. Cytolytic vaginosis. '
                    'American Journal of Obstetrics and Gynecology 1991; 165:1245-1248.'
                )
            elif diagnosis == 'Vaginite Aeróbia':
                autores = 'Donders et al. (2002)'
                referencia = (
                    'Donders GGG, Vereecken A, Bosmans E, Dekeersmaecker A, Salembier G, Spitz B. '
                    'Definition of a type of abnormal vaginal flora that is distinct from bacterial vaginosis: '
                    'aerobic vaginitis. British Journal of Obstetrics and Gynaecology 2002; 109:34-43.'
                )
            else:
                autores = 'Nugent et al. (1991)'
                referencia = (
                    'Nugent RP, Krohn MA, Hillier SL. Reliability of diagnosing bacterial vaginosis '
                    'is improved by a standardized method of Gram stain interpretation. '
                    'Journal of Clinical Microbiology 1991; 29:297-301.'
                )
            # Gera nome do arquivo de saída
            safe_name = name.strip().replace(' ', '_')
            out_docx = f'Laudo - {safe_name}.docx'
            # Renderiza e salva
            doc = DocxTemplate(tpl_path)
            for i, img in enumerate(cropped_imgs, 1):
                img_path = f'tmp_{i}.png'
                img.save(img_path)
                tmp_imgs.append(img_path)
            context = {
                'nome': name,
                'data_coleta': date_col.strftime('%d/%m/%Y'),
                'data_hoje': today_sp,
                'diagnostico': diagnosis,
                'conclusao_diagnostico': DIAGNOSES.get(diagnosis, ''),
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
            doc.save(out_docx)
            # Download
            with open(out_docx, 'rb') as f:
                st.download_button(
                    '⬇️ Baixar .docx', data=f.read(), file_name=out_docx
                )
        except Exception as e:
            st.error(f'Falha ao gerar laudo: {e}')
        finally:
            paths = ([tpl_path] if tpl_path else []) + tmp_imgs + ([out_docx] if out_docx else [])
            for p in paths:
                if p and os.path.exists(p):
                    os.remove(p)

if __name__ == '__main__':
    main()
