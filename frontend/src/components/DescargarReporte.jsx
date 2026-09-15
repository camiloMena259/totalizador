import { useState } from 'react';

function nombrePorDefecto(bancoLabel) {
  const fecha = new Date().toISOString().slice(0, 10);
  const banco = (bancoLabel || 'extracto').toLowerCase().replace(/\s+/g, '-');
  return `reporte-${banco}-${fecha}`;
}

export default function DescargarReporte({ onDescargar, bancoLabel, descargando }) {
  const [nombreArchivo, setNombreArchivo] = useState(() => nombrePorDefecto(bancoLabel));
  const [errorLocal, setErrorLocal] = useState(null);

  const descargar = async () => {
    const nombre = nombreArchivo.trim();
    if (!nombre) {
      setErrorLocal('Escribí un nombre para el archivo.');
      return;
    }
    setErrorLocal(null);
    try {
      await onDescargar(nombre);
    } catch (err) {
      setErrorLocal(err.message);
    }
  };

  return (
    <section className="card descarga-reporte">
      <div className="card__header">
        <h2 className="card__title">Descargar reporte</h2>
        <p className="card__hint">Excel con banco, resumen general, detalle y movimientos.</p>
      </div>

      <div className="descarga-reporte__row">
        <div className="field descarga-reporte__campo">
          <label htmlFor="nombre-reporte">Nombre del archivo</label>
          <input
            id="nombre-reporte"
            type="text"
            value={nombreArchivo}
            onChange={(e) => setNombreArchivo(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') descargar();
            }}
            placeholder="reporte-extracto"
            disabled={descargando}
          />
        </div>

        <div className="carga-card__accion">
          <button
            type="button"
            className="btn btn-primary"
            onClick={descargar}
            disabled={descargando}
          >
            {descargando && <span className="spinner" />}
            {descargando ? 'Generando…' : 'Descargar Excel'}
          </button>
        </div>
      </div>

      {errorLocal && (
        <div className="alert alert-error" role="alert" style={{ marginTop: 16, marginBottom: 0 }}>
          <span>⚠️</span>
          <span>{errorLocal}</span>
        </div>
      )}
    </section>
  );
}
