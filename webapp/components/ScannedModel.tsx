'use client'

import { useGLTF } from '@react-three/drei'

type ScannedModelProps = {
  modelPath: string
}

export function ScannedModel({ modelPath, ...props }: ScannedModelProps) {
  const { scene } = useGLTF(modelPath)
  return <primitive object={scene} {...props} />
}
