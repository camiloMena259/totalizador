import { useEffect, useState } from "react";

export default function EtiquetaForm({
  onGuardar,
  etiquetaEditar,
  cancelar,
}) {
  const [etiqueta, setEtiqueta] = useState("");
  const [palabras, setPalabras] = useState("");

  useEffect(() => {
    if (etiquetaEditar) {
      setEtiqueta(etiquetaEditar.etiqueta);
      setPalabras(etiquetaEditar.palabras_clave.join(", "));
    } else {
      setEtiqueta("");
      setPalabras("");
    }
  }, [etiquetaEditar]);

  function submit(e) {
    e.preventDefault();

    onGuardar({
      etiqueta,
      palabras_clave: palabras
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean),
    });
  }

  return (
    <form onSubmit={submit} className="etiqueta-form">
      <div className="etiqueta-form__row">
        <div className="field etiqueta-form__campo-nombre">
          <label htmlFor="etiqueta-nombre">Nombre de la etiqueta</label>
          <input
            id="etiqueta-nombre"
            type="text"
            placeholder="Ej: Servicios públicos"
            value={etiqueta}
            onChange={(e) => setEtiqueta(e.target.value)}
            required
          />
        </div>

        <div className="field etiqueta-form__campo-palabras">
          <label htmlFor="etiqueta-palabras">Palabras clave</label>
          <textarea
            id="etiqueta-palabras"
            rows={2}
            placeholder="GMF, 4X1000, TRANSFERENCIA..."
            value={palabras}
            onChange={(e) => setPalabras(e.target.value)}
          />
          <span className="field__ayuda">Separadas por comas. Se busca coincidencia en el concepto del movimiento.</span>
        </div>
      </div>

      <div className="etiqueta-form__acciones">
        <button type="submit" className="btn btn-primary">
          {etiquetaEditar ? 'Guardar cambios' : 'Agregar etiqueta'}
        </button>

        {etiquetaEditar && (
          <button type="button" onClick={cancelar} className="btn btn-ghost">
            Cancelar
          </button>
        )}
      </div>
    </form>
  );
}
