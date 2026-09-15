// services/extractoService.js
// Única responsabilidad: hablar con el backend. No sabe nada de React
// ni de cómo se pinta el resultado.

const API_BASE = import.meta.env.API_BASE || "http://localhost:8000/api/extractos/totalizar";
const API_REPORTE = import.meta.env.API_REPORTE || "http://localhost:8000/api/extractos/reporte";

// Un endpoint distinto por banco. Agregar un banco nuevo es agregar una
// entrada aquí (y su función extractora en el backend).
export const BANCOS = {
  occidente: { label: 'Banco de Occidente', endpoint: `${API_BASE}/occidente` },
  popular: { label: 'Banco Popular', endpoint: `${API_BASE}/popular` },
  bbva: { label: 'BBVA', endpoint: `${API_BASE}/bbva` },
  avvillas: {label: 'Banco AV Villas', endpoint: `${API_BASE}/avvillas` },
  bancoomeva: {label: 'Bancoomeva', endpoint: `${API_BASE}/bancoomeva`},
  fidubogota: {label: 'Fidu Bogotá', endpoint: `${API_BASE}/fidubogota`},
  cajasocial: {label: 'Caja Social', endpoint: `${API_BASE}/caja_social`},
  davivienda: {label: 'Davivienda', endpoint: `${API_BASE}/davivienda`},
  bogota: {label: 'Banco de Bogotá', endpoint: `${API_BASE}/bogota`},
};

export async function totalizarExtracto(archivo, banco) {
  const config = BANCOS[banco];
  if (!config) {
    throw new Error(`Banco no soportado: ${banco}`);
  }

  const formData = new FormData();
  formData.append('file', archivo);

  const respuesta = await fetch(config.endpoint, {
    method: 'POST',
    body: formData,
  });

  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({}));
    throw new Error(cuerpo.detail || 'Ocurrió un error al procesar el archivo.');
  }

  return respuesta.json();
}

export async function descargarReporteExcel(resultado, bancoLabel, nombreArchivo) {
  const respuesta = await fetch(API_REPORTE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...resultado,
      banco: bancoLabel,
      nombre_archivo: nombreArchivo,
    }),
  });

  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({}));
    throw new Error(cuerpo.detail || 'No se pudo generar el Excel.');
  }

  const blob = await respuesta.blob();
  const nombre = nombreArchivo.toLowerCase().endsWith('.xlsx')
    ? nombreArchivo
    : `${nombreArchivo}.xlsx`;

  const url = URL.createObjectURL(blob);
  const enlace = document.createElement('a');
  enlace.href = url;
  enlace.download = nombre;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  URL.revokeObjectURL(url);
}
