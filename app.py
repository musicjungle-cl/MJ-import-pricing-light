import streamlit as st
import pandas as pd
import math
import io

# --- CONFIGURACIÓN ---
RATIOS_PESO = {
    "LP": 1.0, "2-LP": 1.9, "3-LP": 2.8, 
    "CD": 0.2, "2-CD": 0.4, "Cassette": 0.25
}

def redondear_900(valor):
    base = math.ceil(valor / 1000) * 1000
    return base - 100 if base - 100 >= valor else base + 900

st.set_page_config(page_title="Calculadora Bertus", layout="wide")
st.title("📀 Importación Directa por Copy-Paste")

# --- SIDEBAR: COSTOS ADUANA ---
with st.sidebar:
    st.header("Costos Chile (CLP)")
    iva_import = st.number_input("IVA Importación", value=436542.0)
    derechos = st.number_input("Derechos Aduana", value=130048.0)
    proc_entrada = st.number_input("Proceso de Entrada", value=157863.0)
    iva_agente = st.number_input("IVA Agente", value=29994.0)
    
    st.header("Logística")
    flete_eur = st.number_input("Flete Europa (EUR)", value=376.76)
    tasa_cambio = st.number_input("Tasa de Cambio", value=1000.0)

# --- ÁREA DE PEGADO ---
st.header("1. Pega tus datos")
st.info("Copia las columnas desde Excel o Word y pégalas aquí abajo.")

texto_pegado = st.text_area("Pega aquí (Artista-Título, Config, Qty, Precio)", height=150)

if texto_pegado:
    # Convertir el texto pegado en un DataFrame
    # El separador '\t' funciona si vienes de Excel/Word
    df = pd.read_csv(io.StringIO(texto_pegado), sep='\t', names=['Titulo', 'Config', 'Qty', 'Precio_EUR'], header=None)
    
    st.header("2. Revisa y Edita los datos")
    st.warning("Si las columnas no se ven alineadas, ajusta los valores en la tabla de abajo:")
    
    # Permitimos editar por si el copy-paste falló en algo
    df_editado = st.data_editor(df, num_rows="dynamic", use_container_width=True)

    if st.button("🚀 Calcular Precios Finales"):
        # Cálculos de prorrateo
        df_editado['Peso_U'] = df_editado['Config'].str.upper().map(RATIOS_PESO).fillna(1.0)
        df_editado['Peso_T'] = df_editado['Peso_U'] * df_editado['Qty']
        
        # Transporte
        flete_clp = flete_eur * tasa_cambio
        df_editado['Flete_U'] = (df_editado['Peso_U'] / df_editado['Peso_T'].sum()) * flete_clp
        
        # Impuestos (Proporcional al valor)
        df_editado['Valor_Neto_U'] = (df_editado['Precio_EUR'] * tasa_cambio) + df_editado['Flete_U']
        ratio_imp = (iva_import + derechos) / (df_editado['Valor_Neto_U'] * df_editado['Qty']).sum()
        df_editado['Impuestos_U'] = df_editado['Valor_Neto_U'] * ratio_imp
        
        # Gastos Fijos (Por unidad)
        gastos_fijos_u = (proc_entrada + iva_agente) / df_editado['Qty'].sum()
        
        # PRECIO FINAL
        df_editado['COSTO_TOTAL'] = df_editado['Valor_Neto_U'] + df_editado['Impuestos_U'] + gastos_fijos_u
        
        # Sugerencias de Venta
        df_editado['VENTA_1.5'] = (df_editado['COSTO_TOTAL'] * 1.5).apply(redondear_900)
        df_editado['VENTA_1.7'] = (df_editado['COSTO_TOTAL'] * 1.7).apply(redondear_900)
        df_editado['VENTA_1.9'] = (df_editado['COSTO_TOTAL'] * 1.9).apply(redondear_900)
        
        st.subheader("3. Resultados")
        st.dataframe(df_editado[['Titulo', 'Config', 'Qty', 'COSTO_TOTAL', 'VENTA_1.5', 'VENTA_1.7', 'VENTA_1.9']].style.format(precision=0))
        
        # Resumen Final
        total_v = (df_editado['COSTO_TOTAL'] * df_editado['Qty']).sum()
        st.metric("Inversión Total Carga (CLP)", f"${total_v:,.0f}")
