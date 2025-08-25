from pyproj import Transformer
import streamlit as st
import ezdxf
import tempfile
import os

# ------------------ Parámetros de Transformación ------------------
ScaleF_fm = 100000000
ScaleX_fm = 859306523.743133
ScaleY_fm = 928246069.040144
OriginX_fm = -824411295
OriginY_fm = -274452409

ScaleF_mf = 100000000
ScaleX_mf = 859306523.743133
ScaleY_mf = 928246069.040144
OriginX_mf = -824411295
OriginY_mf = -274452409

r11_mf = 0.99999999808
r12_mf = 0.00000189215
r13_mf = 0.00006188288
r21_mf = -0.00000189310
r22_mf = 0.99999999988
r23_mf = 0.00001535322
r31_mf = -0.00006188285
r32_mf = -0.00001535333
r33_mf = 0.99999999797
Rotacion_X_mf = 400.00097742351
Rotacion_Y_mf = -0.00393958466
Rotacion_Z_mf = 0.00012051871
S_mf = 1.00000418551
Tx_mf = -170.56218632902
Ty_mf = -407.53693938873
Tz_mf = -104.68954894481

r11_fm = 0.9999999981
r12_fm = -0.0000018931
r13_fm = -0.0000618829
r21_fm = 0.0000018922
r22_fm = 0.9999999999
r23_fm = -0.0000153533
r31_fm = 0.0000618829
r32_fm = 0.0000153532
r33_fm = 0.9999999980
Rotation_X_fm = -0.0009774161
Rotation_Y_fm = 0.0039395865
Rotation_Z_fm = 399.9998795418
S_fm = 0.9999958144
Tx_fm = 170.5687517021
Ty_fm = 407.5369785485
Tz_fm = 104.6722988287

# NUEVO USO DE pyproj:Transformer (más moderno y sin warnings)
transformer_fm_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32719", always_xy=True)
transformer_utm_to_fm = Transformer.from_crs("EPSG:32719", "EPSG:4326", always_xy=True)

# ------------------ Funciones de Transformación ------------------
def transform_coords_mina_to_fr(x_value, y_value, z_value):
    E = S_mf * (r11_mf * y_value + r21_mf * x_value) + Tx_mf
    N = S_mf * (r12_mf * y_value + r22_mf * x_value) + Ty_mf
    Z = S_mf * (r13_mf * y_value + r23_mf * x_value) + Tz_mf
    return E, N, Z

def transform_coords_fr_to_mina(x_value, y_value, z_value):
    E = S_fm * (r11_fm * y_value + r21_fm * x_value) + Tx_fm
    N = S_fm * (r12_fm * y_value + r22_fm * x_value) + Ty_fm
    Z = S_fm * (r13_fm * y_value + r23_fm * x_value) + Tz_fm
    return E, N, Z

def utm_to_decimal(utm_easting, utm_northing):
    lon, lat = transformer_utm_to_fm.transform(utm_easting, utm_northing)
    return lat, lon

def inverse_transform_coords(X_GPS, Y_GPS, Z_GPS):
    x_value = (((X_GPS/360)*(2**32)) - OriginX_mf) * (ScaleX_mf / ScaleF_mf)
    y_value = (((Y_GPS/360)*(2**32)) - OriginY_mf) * (ScaleY_mf / ScaleF_mf)
    z_value = Z_GPS
    return x_value, y_value, z_value

def transform_coords_to_GPS(x_value, y_value, z_value):
    X_GPS = (((x_value * ScaleF_fm / ScaleX_fm) + OriginX_fm) * 360) / (2**32)
    Y_GPS = (((y_value * ScaleF_fm / ScaleY_fm) + OriginY_fm) * 360) / (2**32)
    Z_GPS = z_value
    return X_GPS, Y_GPS, Z_GPS

# ------------------ Procesamiento DXF ------------------
def procesar_archivo_dxf_mina_to_fr(input_path, output_path):
    try:
        doc_1 = ezdxf.readfile(input_path)
        msp_1 = doc_1.modelspace()
        for entity in msp_1.query('LINE CIRCLE ARC LWPOLYLINE POLYLINE'):
            if entity.dxftype() == 'LINE':
                start_y, start_x, _ = transform_coords_mina_to_fr(entity.dxf.start.x, entity.dxf.start.y, 0)
                end_y, end_x, _ = transform_coords_mina_to_fr(entity.dxf.end.x, entity.dxf.end.y, 0)
                entity.dxf.start = (start_x, start_y, 0)
                entity.dxf.end = (end_x, end_y, 0)
            elif entity.dxftype() == 'LWPOLYLINE':
                points = []
                for point in entity.get_points('xy'):
                    y, x = point[:2]
                    E, N, _ = transform_coords_mina_to_fr(x, y, 0)
                    points.append((E, N, 0))
                new_polyline = msp_1.add_polyline3d(points)
                msp_1.delete_entity(entity)
            elif entity.dxftype() == 'POLYLINE':
                for vertex in entity.vertices:
                    y, x, z = vertex.dxf.location
                    E, N, Z = transform_coords_mina_to_fr(x, y, z)
                    vertex.dxf.location = (E, N, Z)
            elif entity.dxftype() in ['CIRCLE', 'ARC']:
                y, x, z = entity.dxf.center
                center_y, center_x, center_z = transform_coords_mina_to_fr(x, y, z)
                entity.dxf.center = (center_x, center_y, center_z)
        doc_1.saveas(output_path)

        doc_2 = ezdxf.readfile(output_path)
        msp_2 = doc_2.modelspace()
        for entity in msp_2.query('LINE CIRCLE ARC LWPOLYLINE POLYLINE 3DFACE'):
            if entity.dxftype() == 'LINE':
                start_x, start_y, _ = entity.dxf.start
                end_x, end_y, _ = entity.dxf.end
                start_lat, start_lon = utm_to_decimal(start_x, start_y)
                end_lat, end_lon = utm_to_decimal(end_x, end_y)
                entity.dxf.start = (start_lon, start_lat, 0)
                entity.dxf.end = (end_lon, end_lat, 0)
            elif entity.dxftype() == 'POLYLINE' or entity.dxftype() == 'LWPOLYLINE':
                if entity.dxftype() == 'LWPOLYLINE':
                    points = entity.get_points('xy')
                    new_points = [utm_to_decimal(x, y) for x, y in points]
                    entity.set_points(new_points, format='xy')
                else:
                    for vertex in entity.vertices:
                        x, y, z = vertex.dxf.location
                        lat, lon = utm_to_decimal(x, y)
                        vertex.dxf.location = (lon, lat, z)
            elif entity.dxftype() == '3DFACE':
                for i in range(4):
                    x, y, z = entity.get_points()[i][:3]
                    lat, lon = utm_to_decimal(x, y)
                    entity.set_point(i, (lon, lat, z))
        doc_2.saveas(output_path)

        doc_3 = ezdxf.readfile(output_path)
        msp_3 = doc_3.modelspace()
        for entity in msp_3.query('LINE CIRCLE ARC LWPOLYLINE POLYLINE'):
            if entity.dxftype() == 'LINE':
                start_x, start_y, start_z = inverse_transform_coords(entity.dxf.start.x, entity.dxf.start.y, entity.dxf.start.z)
                entity.dxf.start = (start_x, start_y, start_z)
                end_x, end_y, end_z = inverse_transform_coords(entity.dxf.end.x, entity.dxf.end.y, entity.dxf.end.z)
                entity.dxf.end = (end_x, end_y, end_z)
            elif entity.dxftype() == 'LWPOLYLINE':
                points = entity.get_points('xy')
                new_points = [inverse_transform_coords(x, y, 0) for x, y in points]
                entity.set_points(new_points, format='xy')
            elif entity.dxftype() == 'POLYLINE':
                points = list(entity.points())
                new_points = [inverse_transform_coords(x, y, z) for x, y, z in points]
                for i, vertex in enumerate(entity.vertices):
                    vertex.dxf.location = new_points[i]
            elif entity.dxftype() == 'CIRCLE':
                center_x, center_y, center_z = inverse_transform_coords(entity.dxf.center.x, entity.dxf.center.y, entity.dxf.center.z)
                entity.dxf.center = (center_x, center_y, center_z)
            elif entity.dxftype() == 'ARC':
                center_x, center_y, center_z = inverse_transform_coords(entity.dxf.center.x, entity.dxf.center.y, entity.dxf.center.z)
                entity.dxf.center = (center_x, center_y, center_z)
        doc_3.saveas(output_path)

        # Proceso final: Crear un nuevo DXF con solo POLYLINE
        doc_final = ezdxf.new()
        msp_final = doc_final.modelspace()
        for entity in doc_3.modelspace().query('POLYLINE'):
            points = list(entity.points())
            msp_final.add_polyline3d(points)
        doc_final.saveas(output_path)
        return True, "El archivo se procesó satisfactoriamente."
    except Exception as e:
        return False, f"Ha ocurrido un error: {e}"

def procesar_archivo_dxf_fr_to_mina(input_path, output_path):
    try:
        doc = ezdxf.readfile(input_path)
        utm_transformations = {}
        for entity in doc.modelspace().query('LINE CIRCLE ARC LWPOLYLINE POLYLINE'):
            if entity.dxftype() == 'LINE':
                start_x, start_y, start_z = transform_coords_to_GPS(entity.dxf.start.x, entity.dxf.start.y, entity.dxf.start.z)
                end_x, end_y, end_z = transform_coords_to_GPS(entity.dxf.end.x, entity.dxf.end.y, entity.dxf.end.z)
                utm_start = transformer_fm_to_utm.transform(start_x, start_y)
                utm_end = transformer_fm_to_utm.transform(end_x, end_y)
                utm_transformations[entity.dxf.handle] = (
                    utm_start,
                    utm_end
                )
            elif entity.dxftype() == 'LWPOLYLINE':
                for i, point in enumerate(entity):
                    gps_x, gps_y, gps_z = transform_coords_to_GPS(point[0], point[1], 0)
                    utm = transformer_fm_to_utm.transform(gps_x, gps_y)
                    utm_transformations[(entity.dxf.handle, i)] = utm
            elif entity.dxftype() == 'POLYLINE':
                for i, vertex in enumerate(entity.vertices):
                    gps_x, gps_y, gps_z = transform_coords_to_GPS(vertex.dxf.location.x, vertex.dxf.location.y, vertex.dxf.location.z)
                    utm = transformer_fm_to_utm.transform(gps_x, gps_y)
                    utm_transformations[(entity.dxf.handle, i)] = utm
            elif entity.dxftype() in ['CIRCLE', 'ARC']:
                center_x, center_y, center_z = transform_coords_to_GPS(entity.dxf.center.x, entity.dxf.center.y, entity.dxf.center.z)
                utm_center = transformer_fm_to_utm.transform(center_x, center_y)
                utm_transformations[entity.dxf.handle] = (utm_center[0], utm_center[1], center_z)

        for entity in doc.modelspace().query('LINE CIRCLE ARC LWPOLYLINE POLYLINE'):
            if entity.dxftype() == 'LINE':
                start_x, start_y = utm_transformations[entity.dxf.handle][0]
                end_x, end_y = utm_transformations[entity.dxf.handle][1]
                entity.dxf.start = (start_x, start_y, entity.dxf.start.z)
                entity.dxf.end = (end_x, end_y, entity.dxf.end.z)
            elif entity.dxftype() == 'LWPOLYLINE':
                new_points = []
                for i, point in enumerate(entity):
                    utm_x, utm_y = utm_transformations[(entity.dxf.handle, i)]
                    new_points.append((utm_x, utm_y, 0))
                entity.set_points(new_points, format='xyb')
            elif entity.dxftype() == 'POLYLINE':
                for i, vertex in enumerate(entity.vertices):
                    utm_x, utm_y = utm_transformations[(entity.dxf.handle, i)]
                    vertex.dxf.location = (utm_x, utm_y, vertex.dxf.location.z)
            elif entity.dxftype() in ['CIRCLE', 'ARC']:
                utm_center_x, utm_center_y, center_z = utm_transformations[entity.dxf.handle]
                entity.dxf.center = (utm_center_x, utm_center_y, center_z)

        for entity in doc.modelspace().query('LINE CIRCLE ARC LWPOLYLINE POLYLINE'):
            if entity.dxftype() == 'LINE':
                start_y, start_x, start_z = transform_coords_fr_to_mina(entity.dxf.start.x, entity.dxf.start.y, entity.dxf.start.z)
                end_y, end_x, end_z = transform_coords_fr_to_mina(entity.dxf.end.x, entity.dxf.end.y, entity.dxf.end.z)
                entity.dxf.start = (start_x, start_y, start_z)
                entity.dxf.end = (end_x, end_y, end_z)
            elif entity.dxftype() == 'LWPOLYLINE':
                new_points = []
                for i in range(len(entity)):
                    y, x, _ = entity[i][:3]
                    E, N, Z = transform_coords_fr_to_mina(x, y, 0)
                    new_points.append((E, N, Z))
                polyline_3d = doc.modelspace().add_polyline3d(new_points)
                doc.modelspace().delete_entity(entity)
            elif entity.dxftype() == 'POLYLINE':
                for vertex in entity.vertices:
                    y, x, z = vertex.dxf.location
                    E, N, Z = transform_coords_fr_to_mina(x, y, 0)
                    vertex.dxf.location = (E, N, z)
            elif entity.dxftype() == 'CIRCLE':
                y, x, z = entity.dxf.center
                center_y, center_x, center_z = transform_coords_fr_to_mina(x, y, z)
                entity.dxf.center = (center_x, center_y, center_z)
            elif entity.dxftype() == 'ARC':
                y, x, z = entity.dxf.center
                center_y, center_x, center_z = transform_coords_fr_to_mina(x, y, z)
                entity.dxf.center = (center_x, center_y, center_z)
        doc.saveas(output_path)

        # Proceso final: Crear un nuevo DXF con solo POLYLINE
        doc_final = ezdxf.new()
        msp_final = doc_final.modelspace()
        for entity in doc.modelspace().query('POLYLINE'):
            points = list(entity.points())
            msp_final.add_polyline3d(points)
        doc_final.saveas(output_path)
        return True, "El archivo se procesó satisfactoriamente."
    except Exception as e:
        return False, f"Ha ocurrido un error: {e}"

# ------------------ Streamlit UI ------------------
st.title("Transformador DXF - ESS|AHS Komatsu")
st.write("Bienvenido al transformador de archivos DXF. Selecciona el archivo de entrada, el tipo de transformación y descarga el resultado.")

# CSS para el spinner de carga
st.markdown("""
<style>
.spinner {
    border: 4px solid #f3f3f3;
    border-top: 4px solid #3498db;
    border-radius: 50%;
    width: 30px;
    height: 30px;
    animation: spin 1s linear infinite;
    margin: 20px auto;
}
@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
</style>
""", unsafe_allow_html=True)

tipo_transformacion = st.selectbox(
    "Seleccione el tipo de transformación:",
    ("FrontRunner® hacia MINA", "MINA hacia FrontRunner®"),
    index=0
)

uploaded_file = st.file_uploader("Sube tu archivo DXF", type=["dxf"])
if uploaded_file:
    st.success("Archivo subido correctamente.")

if tipo_transformacion == "FrontRunner® hacia MINA":
    modo = "fr_to_mina"
else:
    modo = "mina_to_fr"

if uploaded_file:
    if st.button("Procesar DXF"):
        # Mostrar spinner
        spinner_placeholder = st.empty()
        spinner_placeholder.markdown('<div class="spinner"></div>', unsafe_allow_html=True)
        
        # Guardar archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix='.dxf') as tmp_in:
            tmp_in.write(uploaded_file.getvalue())
            tmp_in.flush()
            tmp_in_path = tmp_in.name
        tmp_out_path = tmp_in_path + "_out.dxf"

        # Procesar archivo
        if modo == "mina_to_fr":
            ok, msg = procesar_archivo_dxf_mina_to_fr(tmp_in_path, tmp_out_path)
        else:
            ok, msg = procesar_archivo_dxf_fr_to_mina(tmp_in_path, tmp_out_path)
        
        # Ocultar spinner
        spinner_placeholder.empty()
        
        st.info(f"Resultado procesamiento: {msg}")
        if ok and os.path.exists(tmp_out_path):
            with open(tmp_out_path, "rb") as f:
                st.download_button("Descargar DXF transformado", f.read(), file_name="transformado.dxf", mime="application/dxf")
            os.remove(tmp_out_path)
        else:
            st.error("No se generó archivo de salida. Revisa el archivo fuente y los parámetros.")
        os.remove(tmp_in_path)

