// components/ResumenPorEtiquetaTabla.jsx
import './tablas.css';

const formatoMoneda = new Intl.NumberFormat('es-CO', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export default function ResumenPorEtiquetaTabla({ resumenPorEtiqueta }) {
  const totales = resumenPorEtiqueta.reduce(
    (acc, fila) => ({
      cantidad: acc.cantidad + (fila.cantidad ?? 0),
      debitos: acc.debitos + (fila.total_debitos ?? 0),
      creditos: acc.creditos + (fila.total_creditos ?? 0),
    }),
    { cantidad: 0, debitos: 0, creditos: 0 }
  );

  return (
    <div className="tablas-scope">
      <div className="tabla-card">
        <div className="tabla-header">
          <h2 className="tabla-titulo">
            Resumen por etiqueta
            <span className="conteo">{resumenPorEtiqueta.length}</span>
          </h2>
        </div>

        <div className="tabla-wrapper">
          <table className="tabla">
            <thead>
              <tr>
                <th>Etiqueta</th>
                <th className="num">Cantidad</th>
                <th className="num">Total débitos</th>
                <th className="num">Total créditos</th>
              </tr>
            </thead>
            <tbody>
              {resumenPorEtiqueta.map((fila) => (
                <tr key={fila.etiqueta}>
                  <td>
                    <span className="badge-etiqueta">{fila.etiqueta}</span>
                  </td>
                  <td className="num">{fila.cantidad}</td>
                  <td className="num">
                    {fila.total_debitos ? (
                      <span className="valor-debito">
                        {formatoMoneda.format(fila.total_debitos)}
                      </span>
                    ) : (
                      <span className="valor-cero">—</span>
                    )}
                  </td>
                  <td className="num">
                    {fila.total_creditos ? (
                      <span className="valor-credito">
                        {formatoMoneda.format(fila.total_creditos)}
                      </span>
                    ) : (
                      <span className="valor-cero">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="fila-total">
                <td>Total</td>
                <td className="num">{totales.cantidad}</td>
                <td className="num">{formatoMoneda.format(totales.debitos)}</td>
                <td className="num">{formatoMoneda.format(totales.creditos)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  );
}