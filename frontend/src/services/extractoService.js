// services/extractoService.js
// Única responsabilidad: hablar con el backend. No sabe nada de React
// ni de cómo se pinta el resultado.

//export const API_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/extractos/totalizar";
const API_BASE = 'http://localhost:8000/api/extractos/totalizar';

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
