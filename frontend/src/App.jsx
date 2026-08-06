// App.jsx
// Única responsabilidad: manejar el estado del formulario y orquestar
// la llamada al backend. La presentación vive en components/.

import { useState } from 'react';
import { totalizarExtracto, BANCOS } from './services/extractoService';

import ResumenTarjetas from './components/ResumenTarjetas';
import ResumenPorEtiquetaTabla from './components/ResumenPorEtiquetaTabla';
import MovimientosTabla from './components/MovimientosTabla';
import EtiquetasPage from './pages/EtiquetasPage';

import './styles/theme.css';
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
    <main className="app-shell">
      <header className="app-header">
        <div className="app-header__text">
          <span className="app-eyebrow">Extractos bancarios</span>
          <h1 className="app-title">Totalizador de extractos</h1>
          <p className="app-subtitle">
            Cargá un extracto en PDF y obtené el resumen de movimientos, etiquetado y totalizado.
          </p>
        </div>

        <nav className="nav-tabs" aria-label="Vistas">
          <button
            type="button"
            className={`nav-tabs__btn ${vista === 'totalizador' ? 'activo' : ''}`}
            onClick={() => setVista('totalizador')}
          >
            Totalizador
          </button>
          <button
            type="button"
            className={`nav-tabs__btn ${vista === 'etiquetas' ? 'activo' : ''}`}
            onClick={() => setVista('etiquetas')}
          >
            Etiquetas
          </button>
        </nav>
      </header>

      {vista === 'etiquetas' ? (
        <EtiquetasPage />
      ) : (
        <>
          <section className="card">
            <div className="card__header">
              <h2 className="card__title">Cargar extracto</h2>
            </div>

            <div className="carga-card__row">
              <div className="field carga-card__campo-banco">
                <label htmlFor="banco">Banco</label>
                <select
                  id="banco"
                  value={bancoSeleccionado}
                  onChange={onBancoSeleccionado}
                >
                  {Object.entries(BANCOS).map(([clave, { label }]) => (
                    <option key={clave} value={clave}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="field carga-card__campo-archivo">
                <label htmlFor="archivo">Archivo PDF</label>
                <div className={`dropzone ${archivoSeleccionado ? 'tiene-archivo' : ''}`}>
                  <span className="dropzone__icon">📄</span>
                  <div className="dropzone__text">
                    <strong>
                      {archivoSeleccionado ? archivoSeleccionado.name : 'Elegí o arrastrá un PDF'}
                    </strong>
                    <span>
                      {archivoSeleccionado
                        ? `${(archivoSeleccionado.size / 1024).toFixed(0)} KB`
                        : 'Solo archivos .pdf'}
                    </span>
                  </div>
                  <input
                    id="archivo"
                    type="file"
                    accept="application/pdf"
                    onChange={onArchivoSeleccionado}
                  />
                </div>
              </div>

              <div className="carga-card__accion">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={procesarExtracto}
                  disabled={!archivoSeleccionado || cargando}
                >
                  {cargando && <span className="spinner" />}
                  {cargando ? 'Procesando…' : 'Totalizar'}
                </button>
              </div>
            </div>
          </section>

          {error && (
            <div className="alert alert-error" role="alert">
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}

          {!resultado && !error && !cargando && (
            <div className="empty-state" style={{ marginTop: 20 }}>
              <span className="empty-state__icon">🧾</span>
              <strong>Todavía no hay nada para mostrar</strong>
              <span>Elegí el banco correspondiente, cargá el PDF del extracto y tocá "Totalizar" para ver el resumen.</span>
            </div>
          )}

          {resultado && (
            <section className="resultado">
              <h3 className="section-title">Resumen general</h3>
              <ResumenTarjetas resultado={resultado} />

              <h3 className="section-title">Detalle</h3>
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
