// App.jsx
// Única responsabilidad: manejar el estado del formulario y orquestar
// la llamada al backend. La presentación vive en components/.

import { useState } from 'react';
import { totalizarExtracto, BANCOS } from './services/extractoService';

import ResumenTarjetas from './components/ResumenTarjetas';
import ResumenPorEtiquetaTabla from './components/ResumenPorEtiquetaTabla';
import MovimientosTabla from './components/MovimientosTabla';
import EtiquetasPage from './pages/EtiquetasPage';

import './App.css';

export default function App() {
  const [vista, setVista] = useState('totalizador');

  const [bancoSeleccionado, setBancoSeleccionado] = useState('occidente');
  const [archivoSeleccionado, setArchivoSeleccionado] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState(null);

  const onBancoSeleccionado = (event) => {
    setBancoSeleccionado(event.target.value);
    setResultado(null);
    setError(null);
  };

  const onArchivoSeleccionado = (event) => {
    setArchivoSeleccionado(event.target.files?.[0] ?? null);
    setResultado(null);
    setError(null);
  };

  const procesarExtracto = async () => {
    if (!archivoSeleccionado) return;

    setCargando(true);
    setError(null);
    setResultado(null);

    try {
      const respuesta = await totalizarExtracto(
        archivoSeleccionado,
        bancoSeleccionado
      );
      setResultado(respuesta);
    } catch (err) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  };

  return (
    <main className="contenedor">
      <h1>Totalizador de Extractos Bancarios</h1>

      <div
        style={{
          display: 'flex',
          gap: '10px',
          marginBottom: '20px',
        }}
      >
        <button
          onClick={() => setVista('totalizador')}
          disabled={vista === 'totalizador'}
        >
          Totalizador
        </button>

        <button
          onClick={() => setVista('etiquetas')}
          disabled={vista === 'etiquetas'}
        >
          Administrar etiquetas
        </button>
      </div>

      {vista === 'etiquetas' ? (
        <EtiquetasPage />
      ) : (
        <>
          <section className="carga">
            <select
              value={bancoSeleccionado}
              onChange={onBancoSeleccionado}
            >
              {Object.entries(BANCOS).map(([clave, { label }]) => (
                <option key={clave} value={clave}>
                  {label}
                </option>
              ))}
            </select>

            <input
              type="file"
              accept="application/pdf"
              onChange={onArchivoSeleccionado}
            />

            <button
              onClick={procesarExtracto}
              disabled={!archivoSeleccionado || cargando}
            >
              {cargando ? 'Procesando...' : 'Totalizar'}
            </button>
          </section>

          {error && <p className="error">{error}</p>}

          {resultado && (
            <section className="resultado">
              <ResumenTarjetas resultado={resultado} />

              <ResumenPorEtiquetaTabla
                resumenPorEtiqueta={resultado.resumen_por_etiqueta}
              />

              <MovimientosTabla
                movimientos={resultado.movimientos}
              />
            </section>
          )}
        </>
      )}
    </main>
  );
}