'use client'

import { Suspense } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Environment, Center } from '@react-three/drei'
import { ScannedModel } from './ScannedModel'

export function ModelViewer({ modelPath }: { modelPath: string }) {
  return (
    <Canvas camera={{ position: [2, 1.5, 2.5], fov: 45 }} shadows>
      <color attach="background" args={['#1a1a1e']} />
      <ambientLight intensity={0.6} />
      <directionalLight position={[3, 5, 2]} intensity={1.2} castShadow />
      <Suspense fallback={null}>
        <Center>
          <ScannedModel modelPath={modelPath} />
        </Center>
        <Environment preset="city" />
      </Suspense>
      <OrbitControls autoRotate autoRotateSpeed={0.6} enableDamping />
    </Canvas>
  )
}
