// components/MovimientosTabla.jsx
import { useMemo, useState } from 'react';
import './tablas.css';

const formatoMoneda = new Intl.NumberFormat('es-CO', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const CAMPOS_ORDEN = [
  { valor: 'dia', etiqueta: 'Día' },
  { valor: 'concepto', etiqueta: 'Concepto' },
  { valor: 'etiqueta', etiqueta: 'Etiqueta' },
  { valor: 'debito', etiqueta: 'Débito' },
  { valor: 'credito', etiqueta: 'Crédito' },
  { valor: 'saldo', etiqueta: 'Saldo' },
];

const COLUMNAS_NUMERICAS = new Set(['debito', 'credito', 'saldo']);

function renderValor(valor, tipo) {
  if (valor == null || valor === 0) {
    return <span className="valor-cero">—</span>;
  }
  if (tipo === 'credito') {
    return <span className="valor-credito">{formatoMoneda.format(valor)}</span>;
  }
  if (tipo === 'debito') {
    return <span className="valor-debito">{formatoMoneda.format(valor)}</span>;
  }
  return <span className="valor-saldo">{formatoMoneda.format(valor)}</span>;
}

export default function MovimientosTabla({ movimientos }) {
  const [campoOrden, setCampoOrden] = useState('dia');
  const [direccion, setDireccion] = useState('asc');

  const movimientosOrdenados = useMemo(() => {
    const copia = [...movimientos];
    copia.sort((a, b) => {
      const valorA = a[campoOrden];
      const valorB = b[campoOrden];
      let comparacion;
      if (typeof valorA === 'string' || typeof valorB === 'string') {
        comparacion = String(valorA ?? '').localeCompare(String(valorB ?? ''), 'es');
      } else {
        comparacion = (valorA ?? 0) - (valorB ?? 0);
      }
      return direccion === 'asc' ? comparacion : -comparacion;
    });
    return copia;
  }, [movimientos, campoOrden, direccion]);

  function ordenarPorColumna(campo) {
    if (campo === campoOrden) {
      setDireccion((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setCampoOrden(campo);
      setDireccion('asc');
    }
  }

  return (
    <div className="tablas-scope">
      <div className="tabla-card">
        <div className="tabla-header">
          <h2 className="tabla-titulo">
            Movimientos
            <span className="conteo">{movimientos.length}</span>
          </h2>

          <div className="controles-orden">
            <label htmlFor="orden-campo">Ordenar por</label>
            <select
              id="orden-campo"
              value={campoOrden}
              onChange={(e) => setCampoOrden(e.target.value)}
            >
              {CAMPOS_ORDEN.map((c) => (
                <option key={c.valor} value={c.valor}>
                  {c.etiqueta}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="btn-direccion"
              onClick={() => setDireccion((d) => (d === 'asc' ? 'desc' : 'asc'))}
              title={direccion === 'asc' ? 'Ascendente' : 'Descendente'}
              aria-label="Cambiar dirección de orden"
            >
              {direccion === 'asc' ? '↑' : '↓'}
            </button>
          </div>
        </div>

        <div className="tabla-wrapper">
          <table className="tabla">
            <thead>
              <tr>
                {CAMPOS_ORDEN.map((c) => (
                  <th
                    key={c.valor}
                    className={COLUMNAS_NUMERICAS.has(c.valor) ? 'num sortable' : 'sortable'}
                  >
                    <button type="button" onClick={() => ordenarPorColumna(c.valor)}>
                      {c.etiqueta}
                      <span className={`icon-orden ${campoOrden === c.valor ? 'activo' : ''}`}>
                        {campoOrden === c.valor && direccion === 'desc' ? '▼' : '▲'}
                      </span>
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {movimientosOrdenados.map((mov, i) => (
                <tr key={`${mov.dia}-${i}`}>
                  <td>{mov.dia}</td>
                  <td>{mov.concepto}</td>
                  <td>
                    <span className="badge-etiqueta">{mov.etiqueta}</span>
                  </td>
                  <td className="num">{renderValor(mov.debito, 'debito')}</td>
                  <td className="num">{renderValor(mov.credito, 'credito')}</td>
                  <td className="num">
                    {mov.saldo != null ? renderValor(mov.saldo, 'saldo') : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}