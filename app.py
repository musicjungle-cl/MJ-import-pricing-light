import streamlit as st
import pandas as pd
import pdfplumber
import re
import math

# --- CONFIGURACIÓN DE PESOS ---
RATIOS_PESO = {
    "CD": 0.2, "CASSETTE": 0.25, "LP": 1.0, 
    "2-LP": 1.9, "3-LP": 2.8, "2-CD": 0.4, 
    "3-CD": 0.6, "3-DVD": 0.6
}

def redondear_900(valor):
    base = math.ceil(valor / 1000) * 1000
    return base - 100 if base - 100 >= valor else base + 900

def extraer_datos_v2(file):
    datos = []
    flete_eur = 0.0
    
    with pdfplumber.open(file) as pdf:
        full_text = ""
        for page in pdf.pages:
            lines = page.extract_text().split('\n')
            full_text += page.extract_text() + "\n"
            
            for line in lines:
                # Buscamos líneas que empiecen con Barcode (13 dígitos) o el número de Bertus
                # El patrón identifica: Barcode, Título, Config, Qty, Precio
                match = re.search(r'(\d{13})\s+(.*?)\s+(LP|2-LP|3-LP|CD|2-CD|3-CD|3-DVD)\s+(\d+)\s+([\d,\.]+)', line)
                
                if match:
                    barcode, title, config, qty, price = match.groups()
                    datos.append({
                        "Titulo": title.strip(),
                        "Config": config,
                        "Qty": int(qty),
                        "Precio_EUR": float(price.replace('.', '').replace(',', '.')) / 100 if ',' in price and '.' in price else float(price.replace(',', '.'))
                    })

        # Extraer flete (Freight charges) [cite: 52]
        flete_match = re.search(r"Freight charges\s+([\d,\.]+)", full_text)
        if flete_match:
            flete_eur = float(flete_match.group(1).replace('.', '').replace(',', '.'))
            
    return pd.DataFrame(datos), flete_eur

# --- INTERFAZ ---
st.set_page_config(page_title="Importación Bertus", layout="wide")
st.title("📦 Calculadora de Importación Optimizada")

with st.sidebar:
    st.header("1. Archivos y Valores")
    uploaded_file = st.file_uploader("Factura Bertus (PDF)", type="pdf")
    tasa_cambio = st.number_input("Tasa Cambio (EUR/CLP)", value=1000.0)
    
    st.header("2. Internación Chile (CLP)")
    # Basado en los costos de tu imagen 2
    iva_import = st.number_input("IVA Importación", value=436542.0)
    derechos = st.number_input("Derechos Aduana", value=130048.0)
    proc_entrada = st.number_input("Proceso de Entrada", value=157863.0)
    iva_agente = st.number_input("IVA Agente Aduana", value=29994.0)

if uploaded_file:
    df, flete_detectado = extraer_datos_v2(uploaded_file)
    
    if not df.empty:
        st.success(f"✅ {len(df)} productos detectados. Flete: €{flete_detectado}")
        
        # --- CÁLCULOS ---
        df['Peso_U'] = df['Config'].map(RATIOS_PESO).fillna(0.5)
        df['Peso_Total_Linea'] = df['Peso_U'] * df['Qty']
        
        # Prorrateo Transporte (por peso)
        flete_clp = flete_detectado * tasa_cambio
        df['Transp_U_CLP'] = (df['Peso_U'] / df['Peso_Total_Linea'].sum()) * flete_clp
        
        # Prorrateo Impuestos (por valor FOB + Transp)
        df['Valor_Aduana_U'] = (df['Precio_EUR'] * tasa_cambio) + df['Transp_U_CLP']
        ratio_impuestos = (iva_import + derechos) / (df['Valor_Aduana_U'] * df['Qty']).sum()
        df['Impuestos_U_CLP'] = df['Valor_Aduana_U'] * ratio_impuestos
        
        # Prorrateo Gastos Fijos (por unidad)
        gastos_fijos_u = (proc_entrada + iva_agente) / df['Qty'].sum()
        
        # COSTO FINAL Y PRECIOS
        df['Costo_Landed'] = df['Valor_Aduana_U'] + df['Impuestos_U_CLP'] + gastos_fijos_u
        df['Venta_1.5'] = (df['Costo_Landed'] * 1.5).apply(redondear_900)
        df['Venta_1.7'] = (df['Costo_Landed'] * 1.7).apply(redondear_900)
        df['Venta_1.9'] = (df['Costo_Landed'] * 1.9).apply(redondear_900)
        
        st.dataframe(df[['Titulo', 'Config', 'Qty', 'Costo_Landed', 'Venta_1.5', 'Venta_1.7', 'Venta_1.9']].style.format(precision=0))
        
        # RESUMEN
        st.divider()
        c1, c2, c3 = st.columns(3)
        total_landed = (df['Costo_Landed'] * df['Qty']).sum()
        c1.metric("Costo Total (Con IVA)", f"${total_landed:,.0f}")
        c2.metric("Costo Total (Sin IVA)", f"${total_landed/1.19:,.0f}")
        c3.metric("Flete Prorrateado", f"${flete_clp:,.0f} CLP")
    else:
        st.error("No se detectaron productos. Intenta subir el archivo nuevamente.")
