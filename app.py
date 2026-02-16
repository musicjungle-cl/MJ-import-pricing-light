import streamlit as st
import pandas as pd
import math
import io

# --- CONFIGURACIÓN DE PESOS ---
RATIOS_PESO = {
    "LP": 1.0, "2-LP": 1.9, "3-LP": 2.8, 
    "CD": 0.2, "2-CD": 0.4, "3-CD": 0.6,
    "CASSETTE": 0.25, "3-DVD": 0.6
}

def redondear_900(valor):
    base = math.ceil(valor / 1000) * 1000
    return base - 100 if base - 100 >= valor else base + 900

st.set_page_config(page_title="Music Jungle: Importador Masivo", layout="wide")
st.title("📀 Music Jungle: Procesador de Cargas con Barcode")

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Costos Chile (CLP)")
    iva_import = st.number_input("IVA Importación", value=436542.0)
    derechos = st.number_input("Derechos Aduana", value=130048.0)
    proc_entrada = st.number_input("Proceso de Entrada", value=157863.0)
    iva_agente = st.number_input("IVA Agente", value=29994.0)
    
    st.header("2. Logística y Factura")
    flete_eur = st.number_input("Flete Europa (EUR)", value=376.76)
    subtotal_factura_eur = st.number_input("Subtotal Factura Bertus (EUR)", value=2082.45)
    tasa_cambio = st.number_input("Tasa de Cambio", value=1000.0)

# --- ÁREA DE PEGADO MASIVO ---
st.header("1. Pegado de Datos")
st.info("Copia los datos que te entrego en el chat y pégalos aquí abajo. El formato debe ser: Barcode, Titulo, Config, Qty, Precio.")

texto_pegado = st.text_area("Caja de pegado masivo (Ctrl+V)", height=250, placeholder="Barcode\tTitulo\tConfig\tQty\tPrecio")

if texto_pegado:
    try:
        # Convertimos el texto a DataFrame. El separador '\t' es para tabulaciones de Excel/Chat
        df_raw = pd.read_csv(io.StringIO(texto_pegado), sep='\t', header=None, 
                             names=['Barcode', 'Titulo', 'Config', 'Qty', 'Precio_EUR'])
        
        st.subheader("Verificación de datos pegados")
        # Permitimos edición rápida si algo falló en el pegado
        df = st.data_editor(df_raw, use_container_width=True, num_rows="dynamic")

        if st.button("🚀 Procesar Carga y Calcular"):
            # --- VALIDACIÓN FINANCIERA ---
            nett_amount_calculado = (df['Precio_EUR'] * df['Qty']).sum()
            diferencia = abs(nett_amount_calculado - subtotal_factura_eur)
            
            if diferencia < 0.1:
                st.success(f"✅ Factura Cuadrada: €{nett_amount_calculado:,.2f}")
            else:
                st.warning(f"⚠️ Discrepancia: Total productos €{nett_amount_calculado:,.2f} vs Factura €{subtotal_factura_eur:,.2f}")

            # --- CÁLCULOS ---
            df['Peso_U'] = df['Config'].str.upper().map(RATIOS_PESO).fillna(1.0)
            df['Peso_T'] = df['Peso_U'] * df['Qty']
            flete_clp = flete_eur * tasa_cambio
            
            df['Flete_U'] = (df['Peso_U'] / df['Peso_T'].sum()) * flete_clp
            df['Valor_Neto_U'] = (df['Precio_EUR'] * tasa_cambio) + df['Flete_U']
            ratio_imp = (iva_import + derechos) / (df['Valor_Neto_U'] * df['Qty']).sum()
            df['Impuestos_U'] = df['Valor_Neto_U'] * ratio_imp
            gastos_fijos_u = (proc_entrada + iva_agente) / df['Qty'].sum()
            
            df['Costo_Landed'] = df['Valor_Neto_U'] + df['Impuestos_U'] + gastos_fijos_u
            df['Venta_1.5'] = (df['Costo_Landed'] * 1.5).apply(redondear_900)
            df['Venta_1.7'] = (df['Costo_Landed'] * 1.7).apply(redondear_900)
            df['Venta_1.9'] = (df['Costo_Landed'] * 1.9).apply(redondear_900)
            
            # --- RESULTADOS ---
            st.header("2. Tabla de Precios Finales")
            st.dataframe(df[['Barcode', 'Titulo', 'Config', 'Qty', 'Costo_Landed', 'Venta_1.5', 'Venta_1.7', 'Venta_1.9']].style.format(precision=0))
            
            # --- RESUMEN DE INVERSIÓN Y VENTA ---
            st.divider()
            inv_total_clp = (df['Costo_Landed'] * df['Qty']).sum()
            v15 = (df['Venta_1.5'] * df['Qty']).sum()
            v17 = (df['Venta_1.7'] * df['Qty']).sum()
            v19 = (df['Venta_1.9'] * df['Qty']).sum()

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Inversión Carga", f"${inv_total_clp:,.0f}")
            c2.metric("Venta Total (1.5)", f"${v15:,.0f}", f"${v15-inv_total_clp:,.0f} util.")
            c3.metric("Venta Total (1.7)", f"${v17:,.0f}", f"${v17-inv_total_clp:,.0f} util.")
            c4.metric("Venta Total (1.9)", f"${v19:,.0f}", f"${v19-inv_total_clp:,.0f} util.")
    except Exception as e:
        st.error(f"Error al procesar el pegado. Asegúrate de que los datos tengan 5 columnas. Detalle: {e}")
