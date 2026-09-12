import { Group, Circle, Label, Tag, Text } from "react-konva";
import { useState } from "react";

function Evento() {
  const [hover, setHover] = useState(false);

  return (
    <Group
      onMouseEnter={(e) => {
        setHover(true);
        e.target.getStage()!.container().style.cursor = "pointer";
      }}
      onMouseLeave={(e) => {
        setHover(false);
        e.target.getStage()!.container().style.cursor = "default";
      }}
    >
      <Circle
        x={200}
        y={150}
        radius={10}
        fill="red"
      />

      {hover && (
        <Label x={200} y={120}>
          <Tag
            fill="black"
            cornerRadius={5}
          />
          <Text
            text="Evento 1"
            fill="white"
            padding={8}
            fontSize={14}
          />
        </Label>
      )}
    </Group>
  );
}

export default Evento;