import streamlit as st
import pandas as pd
import math

# --- CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Calculadora de Importación Chile", layout="wide")

st.title("📦 Calculadora de Costos de Importación (EUR -> CLP)")
st.markdown("""
Esta herramienta prorratea costos de transporte por peso, impuestos por valor 
y gastos fijos por unidad para determinar tu precio de venta final.
""")

# --- SIDEBAR: PARÁMETROS GLOBALES ---
with st.sidebar:
    st.header("1. Configuración de Divisa")
    tasa_cambio = st.number_input("Tasa de cambio (EUR a CLP)", value=1000.0, step=1.0)
    
    st.header("2. Costos de Internación (CLP)")
    iva_importacion = st.number_input("IVA Importación (CLP)", value=436542.0)
    derechos_aduana = st.number_input("Derechos Aduana (CLP)", value=130048.0)
    proceso_entrada = st.number_input("Proceso de Entrada (CLP)", value=157863.0)
    iva_agente = st.number_input("IVA Agente Aduana (CLP)", value=29994.0)
    
    st.header("3. Logística Europa (EUR)")
    transporte_eur = st.number_input("Transporte en Europa (EUR)", value=50.0)

# --- ENTRADA DE DATOS (FACTURA) ---
st.header("4. Datos de la Factura")
factura_raw = st.text_area(
    "Pega aquí los datos de la tabla de la factura (columnas: Artista-Título, Config, Qty, Nett.Price €)",
    placeholder="Ejemplo: Aqua-Aquarium	LP	2	14,95",
    height=200
)

# Diccionario de pesos según imagen 3
RATING_PESO = {
    "CD": 0.2,
    "Cassette": 0.25,
    "LP": 1.0, # LP Simple
    "2-LP": 1.9, # Promedio de LP doble 1.8 - 2.0
    "3-LP": 2.8 # Estimación proporcional
}

def redondear_900(valor):
    """Redondea al siguiente valor superior terminado en 900"""
    base = math.ceil(valor / 1000) * 1000
    return base - 100 if base - 100 >= valor else base + 900

if factura_raw:
    # Procesamiento simple de texto a DataFrame (asumiendo copiado de Excel/PDF)
    lines = [line.split('\t') for line in factura_raw.strip().split('\n')]
    try:
        df = pd.DataFrame(lines, columns=['Titulo', 'Config', 'Qty', 'Precio_EUR'])
        df['Qty'] = df['Qty'].astype(int)
        df['Precio_EUR'] = df['Precio_EUR'].str.replace(',', '.').astype(float)
        
        # 1. Asignar Pesos
        def asignar_peso(config):
            config = config.upper()
            if "3-LP" in config: return RATING_PESO["3-LP"]
            if "2-LP" in config: return RATING_PESO["2-LP"]
            if "LP" in config: return RATING_PESO["LP"]
            if "CD" in config: return RATING_PESO["CD"]
            return 0.5 # Default

        df['Peso_Unitario'] = df['Config'].apply(asignar_peso)
        df['Peso_Total_Linea'] = df['Peso_Unitario'] * df['Qty']
        
        # --- CÁLCULOS DE PRORRATEO ---
        total_qty = df['Qty'].sum()
        total_peso = df['Peso_Total_Linea'].sum()
        total_fob_eur = (df['Precio_EUR'] * df['Qty']).sum()
        
        # A. Transporte Europa (por peso)
        transporte_clp = transporte_eur * tasa_cambio
        df['Transporte_CLP_Unit'] = (df['Peso_Unitario'] / total_peso) * transporte_clp
        
        # B. Valor Aduanero (FOB CLP + Transporte prorrateado)
        df['Valor_Aduana_Unit'] = (df['Precio_EUR'] * tasa_cambio) + df['Transporte_CLP_Unit']
        total_valor_aduana = (df['Valor_Aduana_Unit'] * df['Qty']).sum()
        
        # C. IVA y Derechos (por valor)
        ratio_impuestos = (iva_importacion + derechos_aduana) / total_valor_aduana
        df['Impuestos_Valor_Unit'] = df['Valor_Aduana_Unit'] * ratio_impuestos
        
        # D. Gastos Fijos Agente (por unidad)
        gastos_fijos_unit = (proceso_entrada + iva_agente) / total_qty
        df['Gastos_Fijos_Unit'] = gastos_fijos_unit
        
        # COSTO TOTAL LANDED UNITARIO
        df['Costo_Final_Unit'] = df['Valor_Aduana_Unit'] + df['Impuestos_Valor_Unit'] + df['Gastos_Fijos_Unit']
        
        # --- PRECIOS DE VENTA ---
        df['Precio_1.5'] = df['Costo_Final_Unit'].apply(lambda x: redondear_900(x * 1.5))
        df['Precio_1.7'] = df['Costo_Final_Unit'].apply(lambda x: redondear_900(x * 1.7))
        df['Precio_1.9'] = df['Costo_Final_Unit'].apply(lambda x: redondear_900(x * 1.9))
        
        # --- MOSTRAR RESULTADOS ---
        st.header("5. Resultados de Costos y Precios Sugeridos")
        st.dataframe(df[['Titulo', 'Config', 'Qty', 'Costo_Final_Unit', 'Precio_1.5', 'Precio_1.7', 'Precio_1.9']].style.format(precision=0))
        
        # --- RESUMEN FINAL ---
        st.divider()
        st.header("6. Resumen de la Carga")
        
        col1, col2 = st.columns(2)
        costo_total_clp_con_iva = df['Costo_Final_Unit'].mul(df['Qty']).sum()
        # El IVA de importación y agente es el 19%
        costo_total_clp_sin_iva = costo_total_clp_con_iva / 1.19
        
        with col1:
            st.metric("Costo Total Carga (Con IVA)", f"${costo_total_clp_con_iva:,.0f} CLP")
            st.metric("Costo Total Carga (Sin IVA)", f"${costo_total_clp_sin_iva:,.0f} CLP")
            
        with col2:
            seleccion_margen = st.selectbox("Selecciona margen para valor total venta:", ["Precio_1.5", "Precio_1.7", "Precio_1.9"])
            venta_total_con_iva = df[seleccion_margen].mul(df['Qty']).sum()
            st.metric("Valor Total Venta (Con IVA)", f"${venta_total_con_iva:,.0f} CLP")
            st.metric("Valor Total Venta (Sin IVA)", f"${venta_total_con_iva / 1.19:,.0f} CLP")

    except Exception as e:
        st.error(f"Error al procesar los datos: {e}. Asegúrate de copiar las columnas correctamente.")

else:
    st.info("Por favor, pega los datos de la factura para comenzar.")
