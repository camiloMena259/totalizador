// components/ResumenPorEtiquetaTabla.jsx

const formatoMoneda = new Intl.NumberFormat('es-CO', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export default function ResumenPorEtiquetaTabla({ resumenPorEtiqueta }) {
  return (
    <>
      <h2>Resumen por etiqueta</h2>
      <table>
        <thead>
          <tr>
            <th>Etiqueta</th>
            <th>Cantidad</th>
            <th>Total débitos</th>
            <th>Total créditos</th>
          </tr>
        </thead>
        <tbody>
          {resumenPorEtiqueta.map((fila) => (
            <tr key={fila.etiqueta}>
              <td>{fila.etiqueta}</td>
              <td>{fila.cantidad}</td>
              <td>{formatoMoneda.format(fila.total_debitos)}</td>
              <td>{formatoMoneda.format(fila.total_creditos)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
  
}
