// components/MovimientosTabla.jsx

const formatoMoneda = new Intl.NumberFormat('es-CO', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export default function MovimientosTabla({ movimientos }) {
  return (
    <>
      <h2>Movimientos</h2>
      <table>
        <thead>
          <tr>
            <th>Día</th>
            <th>Concepto</th>
            <th>Etiqueta</th>
            <th>Débito</th>
            <th>Crédito</th>
            <th>Saldo</th>
          </tr>
        </thead>
        <tbody>
          {movimientos.map((mov, i) => (
            <tr key={`${mov.dia}-${i}`}>
              <td>{mov.dia}</td>
              <td>{mov.concepto}</td>
              <td>{mov.etiqueta}</td>
              <td>{formatoMoneda.format(mov.debito)}</td>
              <td>{formatoMoneda.format(mov.credito)}</td>
              <td>{mov.saldo != null ? formatoMoneda.format(mov.saldo) : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
