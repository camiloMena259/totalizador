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

      setPalabras(
        etiquetaEditar.palabras_clave.join(", ")
      );

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
    <form
      onSubmit={submit}
      style={{
        marginBottom: 30,
        display: "flex",
        flexDirection: "column",
        gap: 10,
        maxWidth: 600,
      }}
    >

      <h2>

        {etiquetaEditar
          ? "Editar etiqueta"
          : "Nueva etiqueta"}

      </h2>

      <input
        placeholder="Etiqueta"
        value={etiqueta}
        onChange={(e) =>
          setEtiqueta(e.target.value)
        }
      />

      <textarea
        rows={4}
        placeholder="GMF,4X1000,TRANSFERENCIA..."
        value={palabras}
        onChange={(e) =>
          setPalabras(e.target.value)
        }
      />

      <div>

        <button type="submit">

          Guardar

        </button>

        {etiquetaEditar && (

          <button
            type="button"
            onClick={cancelar}
            style={{
              marginLeft: 10,
            }}
          >

            Cancelar

          </button>

        )}

      </div>

    </form>
  );
}