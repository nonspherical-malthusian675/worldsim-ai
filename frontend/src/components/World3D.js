import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text, Grid } from '@react-three/drei';
import * as THREE from 'three';

const ZONE_MATERIALS = {
  residential: { color: '#22c55e', opacity: 0.15 },
  industrial: { color: '#f59e0b', opacity: 0.15 },
  commercial: { color: '#3b82f6', opacity: 0.15 },
  road: { color: '#64748b', opacity: 0.3, height: 0.02 },
  park: { color: '#10b981', opacity: 0.12, height: 0.1 },
  power_plant: { color: '#ef4444', opacity: 0.15 },
  water_treatment: { color: '#38bdf8', opacity: 0.15 },
  warehouse: { color: '#f97316', opacity: 0.15 },
};

const DEMO_ZONES = [
  { type: 'residential', x1: 0, y1: 0, x2: 15, y2: 15 },
  { type: 'commercial', x1: 15, y1: 0, x2: 35, y2: 15 },
  { type: 'industrial', x1: 35, y1: 0, x2: 50, y2: 15 },
  { type: 'road', x1: 0, y1: 15, x2: 50, y2: 22 },
  { type: 'park', x1: 0, y1: 35, x2: 25, y2: 50 },
  { type: 'power_plant', x1: 25, y1: 35, x2: 50, y2: 50 },
];

const AGENT_COLORS = {
  vehicle: '#3b82f6',
  human: '#22c55e',
  machine: '#f59e0b',
  energy: '#ef4444',
};

const GRID_SIZE = 50;
const CELL_SIZE = 1;
const SCALE = 0.5;

function ZoneBox({ zone }) {
  const mat = ZONE_MATERIALS[zone.type] || ZONE_MATERIALS.residential;
  const w = (zone.x2 - zone.x1) * CELL_SIZE * SCALE;
  const h = (zone.y2 - zone.y1) * CELL_SIZE * SCALE;
  const x = (zone.x1 + (zone.x2 - zone.x1) / 2) * CELL_SIZE * SCALE - (GRID_SIZE * CELL_SIZE * SCALE) / 2;
  const z = (zone.y1 + (zone.y2 - zone.y1) / 2) * CELL_SIZE * SCALE - (GRID_SIZE * CELL_SIZE * SCALE) / 2;
  const height = mat.height || 0.3;

  return (
    <mesh position={[x, height / 2, z]}>
      <boxGeometry args={[w, height, h]} />
      <meshStandardMaterial color={mat.color} transparent opacity={mat.opacity} />
      <Text
        position={[0, height + 0.2, 0]}
        fontSize={0.6}
        color="rgba(255,255,255,0.5)"
        anchorX="center"
        anchorY="middle"
      >
        {zone.type.replace('_', '\n')}
      </Text>
    </mesh>
  );
}

function Agent3D({ agent, index }) {
  const meshRef = useRef();
  const color = AGENT_COLORS[agent.type] || '#a78bfa';
  const size = agent.type === 'vehicle' ? 0.25 : agent.type === 'machine' ? 0.3 : 0.15;

  useFrame(() => {
    if (meshRef.current) {
      meshRef.current.position.y = Math.sin(Date.now() * 0.002 + index) * 0.05 + size;
    }
  });

  const geometry = useMemo(() => {
    if (agent.type === 'vehicle') return <boxGeometry args={[size, size, size * 1.5]} />;
    if (agent.type === 'machine') return <cylinderGeometry args={[size / 2, size / 2, size, 8]} />;
    return <sphereGeometry args={[size, 8, 8]} />;
  }, [agent.type, size]);

  return (
    <mesh
      ref={meshRef}
      position={[
        agent.x * CELL_SIZE * SCALE - (GRID_SIZE * CELL_SIZE * SCALE) / 2,
        size,
        agent.y * CELL_SIZE * SCALE - (GRID_SIZE * CELL_SIZE * SCALE) / 2,
      ]}
    >
      {geometry}
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={agent.type === 'energy' ? 0.8 : 0.3}
      />
      <pointLight color={color} intensity={agent.type === 'energy' ? 1 : 0.3} distance={3} />
    </mesh>
  );
}

function Agents({ agents }) {
  if (!agents || agents.length === 0) return null;
  return (
    <group>
      {agents.map((agent, i) => (
        <Agent3D key={agent.id || i} agent={agent} index={i} />
      ))}
    </group>
  );
}

function Ground() {
  const size = GRID_SIZE * CELL_SIZE * SCALE;
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]}>
      <planeGeometry args={[size, size]} />
      <meshStandardMaterial color="#0a0a1a" />
    </mesh>
  );
}

function Scene({ state, timeOfDay }) {
  const dirLightRef = useRef();

  useFrame(({ clock }) => {
    if (dirLightRef.current && timeOfDay === 'day') {
      const angle = clock.getElapsedTime() * 0.1;
      dirLightRef.current.position.x = Math.cos(angle) * 20;
      dirLightRef.current.position.z = Math.sin(angle) * 20;
    }
  });

  const ambientIntensity = timeOfDay === 'night' ? 0.2 : 0.5;
  const dirIntensity = timeOfDay === 'night' ? 0.3 : 0.8;
  const skyColor = timeOfDay === 'night' ? '#0a0a2e' : '#1a1a3e';

  return (
    <>
      <color attach="background" args={[skyColor]} />
      <fog attach="fog" args={[skyColor, 20, 50]} />
      <ambientLight intensity={ambientIntensity} />
      <directionalLight ref={dirLightRef} intensity={dirIntensity} position={[10, 15, 10]} castShadow />
      <Ground />
      <Grid
        args={[GRID_SIZE, GRID_SIZE]}
        cellSize={CELL_SIZE * SCALE}
        cellColor="#1a1a3a"
        sectionColor="#2a2a4a"
        position={[0, 0.01, 0]}
        fadeDistance={30}
        infiniteGrid={false}
      />
      {DEMO_ZONES.map((zone, i) => <ZoneBox key={i} zone={zone} />)}
      <Agents agents={state?.agents} />
    </>
  );
}

const World3D = ({ state, timeOfDay = 'day' }) => (
  <div className="world-3d">
    <Canvas camera={{ position: [15, 20, 15], fov: 50 }} shadows>
      <Scene state={state} timeOfDay={timeOfDay} />
      <OrbitControls
        enableDamping
        dampingFactor={0.1}
        minDistance={5}
        maxDistance={40}
        maxPolarAngle={Math.PI / 2.1}
      />
    </Canvas>
    {state?.agents && (
      <div className="canvas-overlay">
        <span>🌍 3D • {state.agents.length} agents</span>
      </div>
    )}
  </div>
);

export default World3D;
