class Vector3 {
  x: number;
  y: number;
  z: number;
  constructor(x = 0, y = 0, z = 0) {
    this.x = x;
    this.y = y;
    this.z = z;
  }
  set(x: number, y: number, z: number) {
    this.x = x;
    this.y = y;
    this.z = z;
    return this;
  }
  copy(other: Vector3) {
    this.x = other.x;
    this.y = other.y;
    this.z = other.z;
    return this;
  }
}

class Euler extends Vector3 {}

class Vector2 {
  x: number;
  y: number;
  constructor(x = 0, y = 0) {
    this.x = x;
    this.y = y;
  }
}

class Scale {
  x = 1;
  y = 1;
  z = 1;
  setScalar(value: number) {
    this.x = value;
    this.y = value;
    this.z = value;
  }
}

class Object3D {
  name = '';
  children: any[] = [];
  position = new Vector3();
  rotation = new Euler();
  scale = new Scale();
  userData: Record<string, any> = {};
  add(obj: any) {
    this.children.push(obj);
  }
  remove(obj: any) {
    this.children = this.children.filter(child => child !== obj);
  }
  traverse(callback: (obj: any) => void) {
    callback(this);
    for (const child of this.children) {
      if (child && typeof child.traverse === 'function') {
        child.traverse(callback);
      } else {
        callback(child);
      }
    }
  }
  getObjectByName(name: string) {
    if (this.name === name) return this;
    for (const child of this.children) {
      if (child && typeof child.getObjectByName === 'function') {
        const found = child.getObjectByName(name);
        if (found) return found;
      } else if (child?.name === name) {
        return child;
      }
    }
    return null;
  }
}

class Scene extends Object3D {
  background: any = null;
  fog: any = null;
}

class Group extends Object3D {}

class LineBasicMaterial {
  color: Color;
  opacity: number;
  transparent: boolean;
  needsUpdate = false;
  constructor(opts: { color?: number; opacity?: number; transparent?: boolean } = {}) {
    this.color = new Color(opts.color ?? 0);
    this.opacity = opts.opacity ?? 1;
    this.transparent = Boolean(opts.transparent);
  }
  dispose() {}
}

class BufferGeometry {
  attributes: Record<string, any> = {};
  setAttribute(name: string, attr: any) {
    this.attributes[name] = attr;
  }
  dispose() {}
}

class Float32BufferAttribute {
  array: any;
  itemSize: number;
  constructor(array: any, itemSize: number) {
    this.array = array;
    this.itemSize = itemSize;
  }
}

class LineSegments extends Object3D {
  geometry: any;
  material: any;
  constructor(geometry: any, material: any) {
    super();
    this.geometry = geometry;
    this.material = material;
  }
}

class Color {
  value: number;
  constructor(value = 0) {
    this.value = value;
  }
  setHex(value: number) {
    this.value = value;
    return this;
  }
  copy(other: Color) {
    this.value = other.value;
    return this;
  }
  lerp(other: Color, _t: number) {
    this.value = other.value;
    return this;
  }
}

class PlaneGeometry {
  width: number;
  height: number;
  constructor(width: number, height: number) {
    this.width = width;
    this.height = height;
  }
  dispose() {}
}

class MeshBasicMaterial {
  color: Color;
  opacity: number;
  transparent: boolean;
  side: any;
  constructor(opts: { color?: number; opacity?: number; transparent?: boolean; side?: any } = {}) {
    this.color = new Color(opts.color ?? 0);
    this.opacity = opts.opacity ?? 1;
    this.transparent = Boolean(opts.transparent);
    this.side = opts.side;
  }
  dispose() {}
}

class Mesh extends Object3D {
  geometry: any;
  material: any;
  constructor(geometry: any, material: any) {
    super();
    this.geometry = geometry;
    this.material = material;
  }
}

class Texture {
  colorSpace: any = null;
  needsUpdate = false;
}

class TextureLoader {
  load(_url: string, onLoad?: (texture: Texture) => void, _onProgress?: any, _onError?: any) {
    const texture = new Texture();
    if (onLoad) onLoad(texture);
    return texture;
  }
}

class Raycaster {
  setFromCamera(_vec: any, _camera: any) {}
  intersectObjects(_objects: any[]) {
    return [];
  }
}

class PerspectiveCamera extends Object3D {
  fov: number;
  aspect: number;
  near: number;
  far: number;
  constructor(fov: number, aspect: number, near: number, far: number) {
    super();
    this.fov = fov;
    this.aspect = aspect;
    this.near = near;
    this.far = far;
  }
  updateProjectionMatrix() {}
}

class WebGLRenderer {
  domElement: HTMLCanvasElement;
  constructor(_opts: any = {}) {
    this.domElement = document.createElement('canvas');
  }
  setSize(_w: number, _h: number) {}
  setPixelRatio(_ratio: number) {}
  render(_scene: any, _camera: any) {}
  dispose() {}
}

class Fog {
  color: Color;
  near: number;
  far: number;
  constructor(color: number, near: number, far: number) {
    this.color = new Color(color);
    this.near = near;
    this.far = far;
  }
}

const MathUtils = {
  clamp(value: number, min: number, max: number) {
    return Math.min(max, Math.max(min, value));
  },
};

const DoubleSide = 0;
const SRGBColorSpace = 'srgb';

export {
  Scene,
  PerspectiveCamera,
  WebGLRenderer,
  Group,
  LineBasicMaterial,
  BufferGeometry,
  Float32BufferAttribute,
  LineSegments,
  Vector2,
  Raycaster,
  Color,
  PlaneGeometry,
  MeshBasicMaterial,
  Mesh,
  Texture,
  TextureLoader,
  Euler,
  Vector3,
  Fog,
  MathUtils,
  DoubleSide,
  SRGBColorSpace,
};
