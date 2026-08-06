// components/ResumenTarjetas.jsx
// Solo presentación: recibe los totales ya calculados y los muestra.

const formatoMoneda = new Intl.NumberFormat('es-CO', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export default function ResumenTarjetas({ resultado }) {
  const tarjetas = [
    { etiqueta: 'Total Gravamen (4x1000)', valor: resultado.total_gravamen },
    { etiqueta: 'Total Intereses', valor: resultado.total_intereses },
    { etiqueta: 'Total Débitos', valor: resultado.total_debitos },
    { etiqueta: 'Total Créditos', valor: resultado.total_creditos },
  ];

  return (
    <div className="tarjetas">
      {tarjetas.map((t) => (
        <div className="tarjeta" key={t.etiqueta}>
          <span className="etiqueta">{t.etiqueta}</span>
          <span className="valor">{formatoMoneda.format(t.valor)}</span>
        </div>
      ))}
    </div>
  );
}
