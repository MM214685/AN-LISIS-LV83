# -*- coding: utf-8 -*-
"""
Created on Fri Oct 16 16:23:21 2026

@author: meseg
"""

import streamlit as st
import pandas as pd
import numpy as np
import io
import plotly.express as px

st.set_page_config(page_title="Dashboard BEI", layout="wide")

MESES_ORDEN = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
               'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

@st.cache_data
def cargar_y_limpiar_datos(file):
    df_raw = pd.read_excel(file, header=None)
    header_idx = df_raw[df_raw.apply(lambda r: r.astype(str).str.contains('Proyecto').any(), axis=1)].index
    
    if len(header_idx) == 0:
        return None
        
    df = pd.read_excel(file, skiprows=header_idx[0])
    df = df.dropna(subset=['Mes', 'Proyecto'])
    df['Año'] = df['Mes'].astype(str).str.split('-').str[0]
    df['Mes_Nombre'] = df['Mes'].astype(str).str.split('-').str[1]
    
    def asignar_localidad(row):
        nombre = str(row['Nombre Proyecto']).upper()
        proy = str(row['Proyecto'])
        if 'SUECA' in nombre: return 'Sueca'
        if 'XERACO' in nombre: return 'Xeraco'
        if 'DENIA' in nombre or 'DÉNIA' in nombre: return 'Dénia'
        if 'CALPE' in nombre: return 'Calpe'
        if 'TORREVIEJA' in nombre:
            if proy in ['130170007', '130170008', '130170009', 130170007, 130170008, 130170009]: return 'Torrevieja'
            return None
        if 'GUARDAMAR' in nombre: return 'Guardamar del Segura'
        if 'CARTAGENA' in nombre: return 'Cartagena'
        if 'POBLA DE FARNALS' in nombre: return 'La Pobla de Farnals'
        if 'MAZARRON' in nombre or 'MAZARRÓN' in nombre: return 'Mazarrón'
        if 'AGUILAS' in nombre or 'ÁGUILAS' in nombre: return 'Águilas'
        if 'VILLAITANA' in nombre: return 'Meliá Villaitana'
        if 'SOLPELICANOS' in nombre or 'SOL PELICANOS' in nombre or 'SOLPELÍCANOS' in nombre: return 'Meliá Solpelicanos'
        return None

    df['Localidad'] = df.apply(asignar_localidad, axis=1)
    df_filtrado = df.dropna(subset=['Localidad']).copy()
    
    df_filtrado['Ventas'] = pd.to_numeric(df_filtrado['Ventas'], errors='coerce').fillna(0)
    df_filtrado['Coste Directo'] = pd.to_numeric(df_filtrado['Coste Directo'], errors='coerce').fillna(0)
    
    return df_filtrado

def calcular_margenes(df):
    df['Margen €'] = df['Ventas'] - df['Coste Directo']
    df['Margen %'] = 0.0
    mask_ventas = df['Ventas'] != 0
    df.loc[mask_ventas, 'Margen %'] = df.loc[mask_ventas, 'Margen €'] / df.loc[mask_ventas, 'Ventas']
    
    mask_signo = (df['Margen €'] < 0) & (df['Margen %'] > 0)
    df.loc[mask_signo, 'Margen %'] = df.loc[mask_signo, 'Margen %'] * -1
    return df

def agrupar_datos(df):
    res = df.groupby('Localidad')[['Ventas', 'Coste Directo']].sum().reset_index()
    res = calcular_margenes(res)
    return res.sort_values(by='Margen €', ascending=False).reset_index(drop=True)

# --- FUNCIÓN DE ESTILO DE COLORES ---
def aplicar_estilo_color(df):
    formato = {}
    for c in df.columns:
        if 'Ventas' in c or 'Coste' in c or 'Margen €' in c:
            formato[c] = '{:,.2f} €'
        elif c == 'Margen %':
            formato[c] = '{:.2%}'
    
    estilo = df.style.format(formato)
    if 'Margen %' in df.columns:
        estilo = estilo.background_gradient(subset=['Margen %'], cmap='RdYlGn', vmin=0.0, vmax=0.10)
    return estilo

st.title("📊 Cuadro de Mandos - Análisis de Resultados BEI")

uploaded_file = st.file_uploader("Sube el archivo Excel de descarga del BEI", type=["xls", "xlsx"])

if uploaded_file:
    df_filtrado = cargar_y_limpiar_datos(uploaded_file)
    
    if df_filtrado is None:
        st.error("No se encontró la cabecera en el archivo Excel. Verifica el formato.")
        st.stop()
        
    años_disp = sorted(df_filtrado['Año'].unique(), reverse=True)
    meses_disp = [m for m in MESES_ORDEN if m in df_filtrado['Mes_Nombre'].unique()]
    
    st.sidebar.header("Filtros de Análisis")
    año_actual = st.sidebar.selectbox("Año Actual (Ej. 2026)", años_disp)
    año_previo = st.sidebar.selectbox("Año Anterior (Ej. 2025)", años_disp, index=1 if len(años_disp)>1 else 0)
    mes_seleccionado = st.sidebar.selectbox("Mes de Análisis", meses_disp)
    
    if st.sidebar.button("Generar Cuadro de Mando"):
        st.session_state['datos_generados'] = True

    if st.session_state.get('datos_generados', False):
        idx_mes = MESES_ORDEN.index(mes_seleccionado)
        meses_ytd = MESES_ORDEN[:idx_mes+1]
        
        df_act_mes = df_filtrado[(df_filtrado['Año'] == año_actual) & (df_filtrado['Mes_Nombre'] == mes_seleccionado)]
        df_prev_mes = df_filtrado[(df_filtrado['Año'] == año_previo) & (df_filtrado['Mes_Nombre'] == mes_seleccionado)]
        df_act_ytd = df_filtrado[(df_filtrado['Año'] == año_actual) & (df_filtrado['Mes_Nombre'].isin(meses_ytd))]
        df_prev_ytd = df_filtrado[(df_filtrado['Año'] == año_previo) & (df_filtrado['Mes_Nombre'].isin(meses_ytd))]
        
        t1 = agrupar_datos(df_prev_mes)
        t2 = agrupar_datos(df_act_mes)
        
        merged_diff = pd.merge(t2, t1, on='Localidad', suffixes=('_Act', '_Prev'), how='outer').fillna(0)
        merged_diff['Dif Margen €'] = merged_diff['Margen €_Act'] - merged_diff['Margen €_Prev']
        merged_diff['Dif Margen % (pp)'] = (merged_diff['Margen %_Act'] - merged_diff['Margen %_Prev']) * 100
        t3 = merged_diff[['Localidad', 'Dif Margen €', 'Dif Margen % (pp)']].sort_values(by='Dif Margen €', ascending=False).reset_index(drop=True)
        
        t4_data = {
            'Temporada': [año_previo, año_actual],
            'Ventas Totales': [t1['Ventas'].sum(), t2['Ventas'].sum()],
            'Costes Totales': [t1['Coste Directo'].sum(), t2['Coste Directo'].sum()]
        }
        t4 = pd.DataFrame(t4_data)
        t4['Margen €'] = t4['Ventas Totales'] - t4['Costes Totales']
        t4['Margen %'] = 0.0
        mask_t4 = t4['Ventas Totales'] != 0
        t4.loc[mask_t4, 'Margen %'] = t4.loc[mask_t4, 'Margen €'] / t4.loc[mask_t4, 'Ventas Totales']
        
        t5_prev = agrupar_datos(df_prev_ytd)
        t5_act = agrupar_datos(df_act_ytd)
        global_prev_ytd = pd.DataFrame([{'Localidad': 'TOTAL GLOBAL', 'Ventas': t5_prev['Ventas'].sum(), 'Coste Directo': t5_prev['Coste Directo'].sum()}])
        global_act_ytd = pd.DataFrame([{'Localidad': 'TOTAL GLOBAL', 'Ventas': t5_act['Ventas'].sum(), 'Coste Directo': t5_act['Coste Directo'].sum()}])
        t5_prev = pd.concat([t5_prev, calcular_margenes(global_prev_ytd)], ignore_index=True)
        t5_act = pd.concat([t5_act, calcular_margenes(global_act_ytd)], ignore_index=True)
        
        tab1, tab2, tab3 = st.tabs(["🗓️ Análisis Mensual", "📈 Acumulado Anual (YTD)", "📊 Gráficos Interactivos"])
        
        with tab1:
            st.subheader(f"Comparativa Solo del Mes: {mes_seleccionado} {año_actual} vs {año_previo}")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Resultados {año_previo}**")
                st.dataframe(aplicar_estilo_color(t1), hide_index=True)
            with col2:
                st.write(f"**Resultados {año_actual}**")
                st.dataframe(aplicar_estilo_color(t2), hide_index=True)
            
            st.write(f"**Diferencia de Crecimiento ({año_actual} respecto a {año_previo})**")
            col3, col4 = st.columns(2)
            with col3:
                st.dataframe(t3.style.format({'Dif Margen €': '{:,.2f} €', 'Dif Margen % (pp)': '{:.2f} pp'}), hide_index=True)
            with col4:
                st.write("**Resumen Global de Ventas y Costes (Todo Sumado)**")
                st.dataframe(aplicar_estilo_color(t4), hide_index=True)

        with tab2:
            st.subheader(f"Acumulado desde Enero hasta {mes_seleccionado} (Desglosado por Servicio)")
            col_a, col_b = st.columns(2)
            with col_a:
                st.write(f"**Acumulado {año_previo}**")
                st.dataframe(aplicar_estilo_color(t5_prev), hide_index=True)
            with col_b:
                st.write(f"**Acumulado {año_actual}**")
                st.dataframe(aplicar_estilo_color(t5_act), hide_index=True)

        with tab3:
            st.subheader(f"📈 Rentabilidad: Comparativa de Margen % ({año_actual})")
            st.write(f"La altura de la línea indica la Rentabilidad (Margen %). Pasa el ratón por los puntos para ver los Euros (€) reales.")
            
            todas_localidades = sorted(df_act_ytd['Localidad'].unique())
            loc_seleccionadas = st.multiselect("Añade o quita servicios para comparar con la Media:", todas_localidades, default=[])
            
            mostrar_textos = st.checkbox("Mostrar importes (Euros) permanentemente sobre las líneas", value=False)
            
            if not loc_seleccionadas:
                st.info("👆 Selecciona al menos un servicio arriba para generar el gráfico.")
            else:
                try:
                    df_graf = df_act_ytd.groupby(['Mes_Nombre', 'Localidad'])[['Ventas', 'Coste Directo']].sum().reset_index()
                    
                    pivot_v = df_graf.pivot(index='Mes_Nombre', columns='Localidad', values='Ventas').reindex(meses_ytd).fillna(0)
                    pivot_c = df_graf.pivot(index='Mes_Nombre', columns='Localidad', values='Coste Directo').reindex(meses_ytd).fillna(0)
                    
                    acum_v = pivot_v.cumsum()
                    acum_c = pivot_c.cumsum()
                    
                    acum_m_eur = acum_v - acum_c
                    acum_m_pct = acum_m_eur / acum_v
                    acum_m_pct = acum_m_pct.replace([np.inf, -np.inf], 0).fillna(0)
                    mask_s = (acum_m_eur < 0) & (acum_m_pct > 0)
                    acum_m_pct[mask_s] = acum_m_pct[mask_s] * -1
                    
                    # Cálculo del Global
                    g_v = pivot_v.sum(axis=1).cumsum()
                    g_c = pivot_c.sum(axis=1).cumsum()
                    g_m_eur = g_v - g_c
                    
                    g_m_pct_global = g_m_eur / g_v
                    g_m_pct_global = g_m_pct_global.replace([np.inf, -np.inf], 0).fillna(0)
                    mask_sg = (g_m_eur < 0) & (g_m_pct_global > 0)
                    g_m_pct_global[mask_sg] = g_m_pct_global[mask_sg] * -1
                    
                    filas = []
                    for mes in meses_ytd:
                        for loc in loc_seleccionadas:
                            if loc in acum_m_eur.columns:
                                val_eur = acum_m_eur.loc[mes, loc]
                                val_pct = acum_m_pct.loc[mes, loc] * 100
                                text_lbl = f"<b>{val_eur:,.0f} €</b>".replace(',', '.')
                                # Forzar el formato de moneda europeo para la caja del ratón
                                vol_str = f"{val_eur:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') + " €"
                                filas.append({'Mes_Nombre': mes, 'Servicio': loc, 'Margen %': val_pct, 'Margen €': val_eur, 'Etiqueta': text_lbl, 'Volumen_Str': vol_str})
                        
                        val_eur_glob = g_m_eur.loc[mes]
                        val_pct_glob = g_m_pct_global.loc[mes] * 100
                        text_glob = f"<b>{val_eur_glob:,.0f} €</b>".replace(',', '.')
                        # Forzar el formato de moneda europeo para la caja del ratón
                        vol_str_glob = f"{val_eur_glob:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') + " €"
                        filas.append({'Mes_Nombre': mes, 'Servicio': 'TOTAL GLOBAL (Media %)', 'Margen %': val_pct_glob, 'Margen €': val_eur_glob, 'Etiqueta': text_glob, 'Volumen_Str': vol_str_glob})
                        
                    df_plot = pd.DataFrame(filas)
                    
                    # Usamos custom_data para meter la variable Volumen_Str en la caja del ratón
                    fig = px.line(df_plot, x='Mes_Nombre', y='Margen %', color='Servicio', 
                                  text='Etiqueta' if mostrar_textos else None, markers=True,
                                  custom_data=['Volumen_Str'])
                    
                    if mostrar_textos:
                        fig.update_traces(textposition="top center")
                        
                    for trace in fig.data:
                        if trace.name == 'TOTAL GLOBAL (Media %)':
                            trace.line.color = 'red'
                            trace.line.width = 4
                            trace.textfont = dict(color='red', size=13)
                        else:
                            trace.line.width = 2
                            trace.textfont = dict(size=12)
                            
                    fig.update_layout(
                        hovermode='x unified',
                        xaxis_title="",
                        yaxis_title="Rentabilidad: Margen Acumulado (%)",
                        yaxis_ticksuffix=" %",
                        legend_title="Servicios (Clic para ocultar/mostrar)"
                    )
                    
                    # Llamamos al Volumen_Str ya formateado en la caja mágica
                    fig.update_traces(hovertemplate='Rentabilidad: %{y:.2f}% <br>Volumen: %{customdata[0]}')
                    
                    fig.update_xaxes(
                        type='category',
                        categoryorder='array',
                        categoryarray=meses_ytd,
                        dtick=1
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.markdown("### 📋 Línea de Tiempo: Margen % Acumulado")
                    st.write("Evolución numérica con escala de colores (Verde = Óptimo >10%, Rojo = Crítico)")
                    
                    df_tabla = df_plot.pivot(index='Servicio', columns='Mes_Nombre', values='Margen %')
                    df_tabla = df_tabla.reindex(columns=meses_ytd)
                    
                    servicios_list = [s for s in df_tabla.index if s != 'TOTAL GLOBAL (Media %)']
                    if 'TOTAL GLOBAL (Media %)' in df_tabla.index:
                        servicios_list.append('TOTAL GLOBAL (Media %)')
                    df_tabla = df_tabla.reindex(servicios_list)
                    
                    st.dataframe(df_tabla.style.format("{:.2f}%").background_gradient(cmap='RdYlGn', vmin=0, vmax=10), use_container_width=True)
                    
                except Exception as e:
                    st.error(f"Error al generar el gráfico: {str(e)}")
            
        st.divider()
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            fmt_moneda = workbook.add_format({'num_format': '#,##0.00 €'})
            fmt_porcentaje = workbook.add_format({'num_format': '0.00%'})
            fmt_pp = workbook.add_format({'num_format': '0.00 "pp"'})
            
            def escribir_tabla(df_to_write, sheet_name, start_row, title):
                df_to_write.to_excel(writer, sheet_name=sheet_name, startrow=start_row+1, index=False)
                worksheet = writer.sheets[sheet_name]
                worksheet.write_string(start_row, 0, title)
                for col_num, col_name in enumerate(df_to_write.columns):
                    if '€' in col_name or 'Ventas' in col_name or 'Coste' in col_name:
                        worksheet.set_column(col_num, col_num, 15, fmt_moneda)
                    elif '%' in col_name and 'pp' not in col_name:
                        worksheet.set_column(col_num, col_num, 12, fmt_porcentaje)
                    elif 'pp' in col_name:
                        worksheet.set_column(col_num, col_num, 15, fmt_pp)
                    else:
                        worksheet.set_column(col_num, col_num, 25)
                return start_row + len(df_to_write) + 4
                
            fila = escribir_tabla(t1, 'Hoja 1 - Mensual', 0, f'1. Resultados {mes_seleccionado} {año_previo}')
            fila = escribir_tabla(t2, 'Hoja 1 - Mensual', fila, f'2. Resultados {mes_seleccionado} {año_actual}')
            fila = escribir_tabla(t3, 'Hoja 1 - Mensual', fila, '3. Diferencias de Margen')
            escribir_tabla(t4, 'Hoja 1 - Mensual', fila, '4. Resumen Global del Mes')
            
            fila2 = escribir_tabla(t5_prev, 'Hoja 2 - Acumulado', 0, f'5a. Acumulado Enero-{mes_seleccionado} ({año_previo})')
            escribir_tabla(t5_act, 'Hoja 2 - Acumulado', fila2, f'5b. Acumulado Enero-{mes_seleccionado} ({año_actual})')

        st.download_button(
            label="⬇️ Descargar Excel Definitivo de Análisis",
            data=output.getvalue(),
            file_name=f"Analisis_{mes_seleccionado}_{año_actual}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )