// components/ResumenTarjetas.jsx
// Solo presentación: recibe los totales ya calculados y los muestra.

const formatoMoneda = new Intl.NumberFormat('es-CO', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export default function ResumenTarjetas({ resultado }) {
  const tarjetas = [
    { etiqueta: 'Gravamen (4x1000)', valor: resultado.total_gravamen, variante: '' },
    { etiqueta: 'Intereses', valor: resultado.total_intereses, variante: '' },
    { etiqueta: 'Total débitos', valor: resultado.total_debitos, variante: 'debito' },
    { etiqueta: 'Total créditos', valor: resultado.total_creditos, variante: 'credito' },
  ];

  return (
    <div className="kpi-grid">
      {tarjetas.map((t) => (
        <div
          className={`kpi-card ${t.variante ? `kpi-card--${t.variante}` : ''}`}
          key={t.etiqueta}
        >
          <span className="kpi-card__label">{t.etiqueta}</span>
          <span className="kpi-card__valor">{formatoMoneda.format(t.valor)}</span>
        </div>
      ))}
    </div>
  );
}
