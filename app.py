import streamlit as st
import pandas as pd
import pdfplumber
import re
import math

# --- CONFIGURACIÓN DE PESOS (Imagen 3) ---
# Basado en los ratios definidos por el usuario
RATIOS_PESO = {
    "CD": 0.2,
    "CASSETTE": 0.25,
    "LP": 1.0,
    "2-LP": 1.9,
    "3-LP": 2.8,
    "2-CD": 0.4,
    "3-CD": 0.6,
    "3-DVD": 0.6
}

def redondear_900(valor):
    base = math.ceil(valor / 1000) * 1000
    return base - 100 if base - 100 >= valor else base + 900

def extraer_datos_bertus(file):
    datos = []
    flete_eur = 0.0
    
    with pdfplumber.open(file) as pdf:
        # 1. Extraer ítems de las tablas
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Buscamos filas que tengan un formato de precio o cantidad
                    # Filtramos por palabras clave de configuración
                    if any(conf in str(row).upper() for conf in RATIOS_PESO.keys()):
                        try:
                            # Limpieza de datos según estructura de la factura
                            # Nota: La posición de las columnas varía según el parseo del PDF
                            # Buscamos Qty y Price por posición relativa o contenido
                            res = [c for c in row if c is not None and c != '']
                            if len(res) >= 5:
                                title = res[2].replace('\n', ' ')
                                config = res[3].replace('\n', ' ').strip().upper()
                                qty = int(res[4])
                                price = float(res[7].replace(',', '.')) if ',' in res[7] else float(res[7])
                                
                                # Normalizar configuración para match con RATIOS
                                config_match = "LP"
                                for k in RATIOS_PESO.keys():
                                    if k in config:
                                        config_match = k
                                        break
                                        
                                datos.append({
                                    "Titulo": title,
                                    "Config": config_match,
                                    "Qty": qty,
                                    "Precio_EUR": price
                                })
                        except:
                            continue
        
        # 2. Extraer Freight Charges del final 
        full_text = "".join([p.extract_text() for p in pdf.pages])
        flete_match = re.search(r"Freight charges\s+([\d,\.]+)", full_text)
        if flete_match:
            flete_eur = float(flete_match.group(1).replace('.', '').replace(',', '.'))
            
    return pd.DataFrame(datos), flete_eur

# --- INTERFAZ STREAMLIT ---
st.title("🚀 Importador Inteligente: Europa -> Chile")

with st.sidebar:
    st.header("1. Cargar Factura PDF")
    uploaded_file = st.file_uploader("Sube el PDF de Bertus", type="pdf")
    
    st.header("2. Costos de Internación (CLP)")
    # Valores por defecto de la imagen 2 [cite: 2]
    iva_import = st.number_input("IVA Importación", value=436542)
    derechos = st.number_input("Derechos Aduana", value=130048)
    proc_entrada = st.number_input("Proceso de Entrada", value=157863)
    iva_agente = st.number_input("IVA Agente", value=29994)
    
    tasa_cambio = st.number_input("Tasa de Cambio (EUR/CLP)", value=1020.0)

if uploaded_file:
    df, flete_detectado = extraer_datos_bertus(uploaded_file)
    
    if not df.empty:
        st.success(f"Factura procesada. Flete detectado: €{flete_detectado}")
        
        # --- LÓGICA DE PRORRATEO ---
        # A. Cálculo de Pesos Relativos
        df['Peso_U'] = df['Config'].map(RATIOS_PESO).fillna(0.5)
        df['Peso_Total_Linea'] = df['Peso_U'] * df['Qty']
        total_peso_carga = df['Peso_Total_Linea'].sum()
        
        # B. Prorrateo Transporte (por peso)
        flete_clp = flete_detectado * tasa_cambio
        df['Transp_U_CLP'] = (df['Peso_U'] / total_peso_carga) * flete_clp
        
        # C. Prorrateo Impuestos (por valor: FOB + Transp)
        df['Valor_Aduana_U'] = (df['Precio_EUR'] * tasa_cambio) + df['Transp_U_CLP']
        total_valor_aduana = (df['Valor_Aduana_U'] * df['Qty']).sum()
        ratio_impuestos = (iva_import + derechos) / total_valor_aduana
        df['Impuestos_U_CLP'] = df['Valor_Aduana_U'] * ratio_impuestos
        
        # D. Prorrateo Gastos Fijos (por unidad)
        gastos_fijos_u = (proc_entrada + iva_agente) / df['Qty'].sum()
        
        # COSTO FINAL LANDED
        df['Costo_Landed'] = df['Valor_Aduana_U'] + df['Impuestos_U_CLP'] + gastos_fijos_u
        
        # PRECIOS DE VENTA
        df['P_Venta_1.5'] = (df['Costo_Landed'] * 1.5).apply(redondear_900)
        df['P_Venta_1.7'] = (df['Costo_Landed'] * 1.7).apply(redondear_900)
        df['P_Venta_1.9'] = (df['Costo_Landed'] * 1.9).apply(redondear_900)
        
        st.header("Resultados de Prorrateo")
        st.dataframe(df[['Titulo', 'Config', 'Qty', 'Costo_Landed', 'P_Venta_1.5', 'P_Venta_1.7', 'P_Venta_1.9']])
        
        # RESUMEN CARGA
        st.divider()
        c1, c2 = st.columns(2)
        total_con_iva = (df['Costo_Landed'] * df['Qty']).sum()
        with c1:
            st.metric("Costo Carga Total (CLP)", f"${total_con_iva:,.0f}")
        with c2:
            st.metric("Total Unidades", f"{df['Qty'].sum()} un.")
    else:
        st.error("No se pudieron extraer datos de la tabla. Revisa el formato del PDF.")
