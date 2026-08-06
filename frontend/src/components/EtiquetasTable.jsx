import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

function FilaEtiqueta({ etiqueta, onEditar, onEliminar }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: etiqueta.etiqueta });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    background: isDragging ? "#f0f0f0" : undefined,
  };

  return (
    <tr ref={setNodeRef} style={style}>
      <td
        {...attributes}
        {...listeners}
        style={{ cursor: "grab", textAlign: "center", width: 30 }}
        title="Arrastrar para cambiar prioridad"
      >
        ⠿
      </td>

      <td>{etiqueta.etiqueta}</td>

      <td>{etiqueta.palabras_clave.join(", ")}</td>

      <td>
        <button onClick={() => onEditar(etiqueta)}>Editar</button>{" "}
        <button onClick={() => onEliminar(etiqueta.etiqueta)}>
          Eliminar
        </button>
      </td>
    </tr>
  );
}

export default function EtiquetasTable({
  etiquetas,
  onEditar,
  onEliminar,
  onReordenar,
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 }, // evita drags accidentales al hacer click
    })
  );

  function handleDragEnd(event) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = etiquetas.findIndex((e) => e.etiqueta === active.id);
    const newIndex = etiquetas.findIndex((e) => e.etiqueta === over.id);

    onReordenar(arrayMove(etiquetas, oldIndex, newIndex));
  }

  return (
    <div>
      <p style={{ color: "#666", fontSize: 14 }}>
        La fila más arriba tiene mayor prioridad: si un concepto matchea
        varias etiquetas, gana la que esté más arriba en la lista.
      </p>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <table width="100%" border="1" cellPadding="8">
          <thead>
            <tr>
              <th></th>
              <th>Etiqueta</th>
              <th>Palabras clave</th>
              <th>Acciones</th>
            </tr>
          </thead>

          <tbody>
            <SortableContext
              items={etiquetas.map((e) => e.etiqueta)}
              strategy={verticalListSortingStrategy}
            >
              {etiquetas.map((e) => (
                <FilaEtiqueta
                  key={e.etiqueta}
                  etiqueta={e}
                  onEditar={onEditar}
                  onEliminar={onEliminar}
                />
              ))}
            </SortableContext>
          </tbody>
        </table>
      </DndContext>
    </div>
  );
}