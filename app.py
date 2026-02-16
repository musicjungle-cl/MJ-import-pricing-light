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

st.set_page_config(page_title="Music Jungle: Gestor de Importación", layout="wide")
st.title("📀 Music Jungle: Calculadora Pro de Importación")

# --- SIDEBAR: COSTOS Y LOGÍSTICA ---
with st.sidebar:
    st.header("1. Costos Chile (CLP)")
    iva_import = st.number_input("IVA Importación", value=436542.0)
    derechos = st.number_input("Derechos Aduana", value=130048.0)
    proc_entrada = st.number_input("Proceso de Entrada", value=157863.0)
    iva_agente = st.number_input("IVA Agente", value=29994.0)
    
    st.header("2. Logística y Factura")
    flete_eur = st.number_input("Flete Europa (EUR)", value=376.76)
    subtotal_factura_eur = st.number_input("Subtotal Factura Bertus (EUR)", value=2082.45)
    tasa_cambio = st.number_input("Tasa de Cambio (EUR/CLP)", value=1000.0)

# --- ENTRADA DE DATOS ---
st.header("1. Ingreso de Productos")
st.info("💡 Pega las 5 columnas: Barcode, Titulo, Config, Qty, Precio_EUR")

# Estado inicial con 5 columnas
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame([
        {"Barcode": "", "Titulo": "", "Config": "LP", "Qty": 1, "Precio_EUR": 0.0}
    ])

df_input = st.data_editor(
    st.session_state.data, 
    num_rows="dynamic", 
    use_container_width=True,
    column_config={
        "Barcode": st.column_config.TextColumn("Barcode"),
        "Config": st.column_config.SelectboxColumn("Config", options=list(RATIOS_PESO.keys())),
        "Precio_EUR": st.column_config.NumberColumn("Precio Unit. €", format="€ %.2f")
    }
)

if st.button("🚀 Procesar y Validar Carga"):
    df = df_input.copy()
    df = df[df['Titulo'] != ""] # Limpiar filas vacías
    
    if not df.empty:
        # --- VALIDACIÓN FINANCIERA ---
        nett_amount_calculado = (df['Precio_EUR'] * df['Qty']).sum()
        diferencia = abs(nett_amount_calculado - subtotal_factura_eur)
        
        if diferencia < 0.01:
            st.success(f"✅ Validación Exitosa: El total ingresado (€{nett_amount_calculado:,.2f}) coincide con el subtotal de la factura.")
        else:
            st.warning(f"⚠️ Discrepancia detectada: El total de los productos es €{nett_amount_calculado:,.2f}, pero el subtotal de la factura es €{subtotal_factura_eur:,.2f} (Dif: €{diferencia:,.2f}).")

        # --- CÁLCULOS DE PRORRATEO ---
        df['Peso_U'] = df['Config'].str.upper().map(RATIOS_PESO).fillna(1.0)
        df['Peso_T'] = df['Peso_U'] * df['Qty']
        total_peso = df['Peso_T'].sum()
        flete_clp = flete_eur * tasa_cambio
        
        # Transporte por peso
        df['Flete_U'] = (df['Peso_U'] / total_peso) * flete_clp
        # Impuestos por valor
        df['Valor_Neto_U'] = (df['Precio_EUR'] * tasa_cambio) + df['Flete_U']
        ratio_imp = (iva_import + derechos) / (df['Valor_Neto_U'] * df['Qty']).sum()
        df['Impuestos_U'] = df['Valor_Neto_U'] * ratio_imp
        # Gastos fijos por unidad
        gastos_fijos_u = (proc_entrada + iva_agente) / df['Qty'].sum()
        
        # Costos y Precios
        df['Costo_Landed'] = df['Valor_Neto_U'] + df['Impuestos_U'] + gastos_fijos_u
        df['Venta_1.5'] = (df['Costo_Landed'] * 1.5).apply(redondear_900)
        df['Venta_1.7'] = (df['Costo_Landed'] * 1.7).apply(redondear_900)
        df['Venta_1.9'] = (df['Costo_Landed'] * 1.9).apply(redondear_900)
        
        # --- RESULTADOS ---
        st.header("2. Tabla de Costos y Precios Finales")
        st.dataframe(
            df[['Barcode', 'Titulo', 'Config', 'Qty', 'Costo_Landed', 'Venta_1.5', 'Venta_1.7', 'Venta_1.9']].style.format(precision=0),
            use_container_width=True
        )
        
        # --- RESUMEN Y PROYECCIÓN DE VENTAS ---
        st.divider()
        st.header("3. Resumen Financiero de la Carga")
        
        inv_total_clp = (df['Costo_Landed'] * df['Qty']).sum()
        
        # Proyecciones de Venta Total
        venta_total_15 = (df['Venta_1.5'] * df['Qty']).sum()
        venta_total_17 = (df['Venta_1.7'] * df['Qty']).sum()
        venta_total_19 = (df['Venta_1.9'] * df['Qty']).sum()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Inversión Total Carga", f"${inv_total_clp:,.0f} CLP")
        with col2:
            st.metric("Valor Venta Total (x1.5)", f"${venta_total_15:,.0f} CLP", delta=f"${venta_total_15 - inv_total_clp:,.0f} Utilidad")
        with col3:
            st.metric("Valor Venta Total (x1.7)", f"${venta_total_17:,.0f} CLP", delta=f"${venta_total_17 - inv_total_clp:,.0f} Utilidad")
        with col4:
            st.metric("Valor Venta Total (x1.9)", f"${venta_total_19:,.0f} CLP", delta=f"${venta_total_19 - inv_total_clp:,.0f} Utilidad")
            
    else:
        st.error("No hay datos para procesar. Pega la información en la tabla superior.")
