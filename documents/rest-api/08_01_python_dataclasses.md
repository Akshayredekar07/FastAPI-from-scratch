# Python Dataclasses: Modern Data Structures for AI Engineering

## Overview

Dataclasses reduce boilerplate for classes that primarily store data. Introduced in Python 3.7 via PEP 557, they automatically generate `__init__`, `__repr__`, `__eq__`, and other special methods. For AI engineers working with FastAPI, ML models, and data pipelines, dataclasses provide clean, type-annotated data containers.

## Basic Dataclass

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class ModelConfig:
    learning_rate: float
    batch_size: int
    epochs: int
    optimizer: str = "adam"
    checkpoint_path: Optional[str] = None
```

Instantiation is straightforward:

```python
config = ModelConfig(
    learning_rate=0.001,
    batch_size=32,
    epochs=100,
    optimizer="adam",
    checkpoint_path="/models/checkpoint.pt"
)

print(config)
# ModelConfig(learning_rate=0.001, batch_size=32, epochs=100, optimizer='adam', checkpoint_path='/models/checkpoint.pt')
```

## Field Configuration with `field()`

The `field()` function provides fine-grained control over individual fields:

```python
from dataclasses import dataclass, field
from typing import List, Optional
import torch

@dataclass
class TrainingData:
    batch_size: int = 32
    shuffle: bool = True
    num_workers: int = 4
    pin_memory: bool = True
    drop_last: bool = False

@dataclass
class ModelSpec:
    input_dim: int
    hidden_dims: List[int] = field(default_factory=list)
    output_dim: int = 1
    activation: str = "relu"
    dropout: float = 0.0

    def build_layers(self) -> List[torch.nn.Module]:
        layers = []
        prev_dim = self.input_dim
        for dim in self.hidden_dims:
            layers.append(torch.nn.Linear(prev_dim, dim))
            layers.append(torch.nn.ReLU() if self.activation == "relu" else torch.nn.Tanh())
            if self.dropout > 0:
                layers.append(torch.nn.Dropout(self.dropout))
            prev_dim = dim
        layers.append(torch.nn.Linear(prev_dim, self.output_dim))
        return layers
```

## Mutable Defaults and the `default_factory` Pattern

Mutable default arguments cause bugs. Use `default_factory` for lists, dicts, and other mutable types:

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class DatasetConfig:
    name: str
    features: List[str] = field(default_factory=list)  # Correct: factory
    target_column: str = "label"
    preprocessing_steps: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

# Usage
dataset = DatasetConfig(
    name="sentiment_data",
    features=["text", "sentiment_score", "word_count"],
    target_column="label",
    preprocessing_steps=["lowercase", "remove_punctuation", "tokenize"]
)

dataset.features.append("embedding")  # Does not affect other instances
```

## Read-Only and Computed Fields

Control field initialization with various `field()` parameters:

```python
from dataclasses import dataclass, field
from typing import List, Optional
import hashlib

@dataclass
class DataRecord:
    id: str
    content: str
    checksum: str = field(init=False)

    def __post_init__(self):
        self.checksum = hashlib.md5(self.content.encode()).hexdigest()

    @property
    def content_hash(self) -> str:
        return self.checksum

@dataclass
class ProcessedBatch:
    batch_id: int
    records: List[DataRecord] = field(default_factory=list)
    total_records: int = field(init=False)

    def __post_init__(self):
        self.total_records = len(self.records)

    @property
    def is_empty(self) -> bool:
        return self.total_records == 0

    @property
    def record_ids(self) -> List[str]:
        return [r.id for r in self.records]
```

## Dataclasses with FastAPI

Dataclasses work seamlessly with FastAPI for request/response models:

```python
from dataclasses import dataclass, field
from typing import List, Optional, Literal
from fastapi import FastAPI, HTTPException

app = FastAPI()

@dataclass
class PredictionRequest:
    model_name: str
    inputs: List[List[float]]
    options: Optional[dict] = None

@dataclass
class PredictionResult:
    model_name: str
    predictions: List[float]
    probabilities: Optional[List[List[float]]] = None
    inference_time_ms: float

@dataclass
class BatchPredictionResponse:
    batch_id: str
    results: List[PredictionResult]
    total_inference_time_ms: float
    successful_count: int
    failed_count: int

@app.post("/predict", response_model=PredictionResult)
async def predict(request: PredictionRequest):
    # Model inference logic here
    return PredictionResult(
        model_name=request.model_name,
        predictions=[0.85, 0.12, 0.03],
        probabilities=None,
        inference_time_ms=12.5
    )
```

## Frozen Dataclasses for Immutability

Frozen dataclasses prevent modification after creation, useful for configuration objects:

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class ModelArchitecture:
    name: str
    input_type: Literal["image", "text", "tabular"]
    output_classes: int
    base_channels: int = 64
    depth: int = 4

# Usage
arch = ModelArchitecture(
    name="resnet50",
    input_type="image",
    output_classes=1000,
    base_channels=64,
    depth=50
)

arch.base_channels = 128  # Raises FrozenInstanceError
arch.name = "efficientnet"  # Raises FrozenInstanceError
```

## Sorting and Comparison

Control comparison behavior for dataclasses:

```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class TrainingExperiment:
    name: str
    accuracy: float
    loss: float
    epoch: int
    model_path: Optional[str] = None

    def __lt__(self, other):
        return self.accuracy < other.accuracy

@dataclass(order=True)
class SortedExperiment:
    sort_index: float = field(init=False, repr=False)
    name: str = field(compare=False)
    accuracy: float
    loss: float

    def __post_init__(self):
        self.sort_index = -self.accuracy  # Negative for descending order

experiments = [
    TrainingExperiment("exp1", 0.85, 0.15, 10),
    TrainingExperiment("exp2", 0.92, 0.08, 15),
    TrainingExperiment("exp3", 0.88, 0.12, 12),
]

sorted_experiments = sorted(experiments)
best = sorted_experiments[-1]  # Highest accuracy
```

## Mermaid Diagram: Dataclass Pattern in ML Pipeline

```mermaid
flowchart LR
    A[TrainingData] --> B[ModelSpec]
    B --> C[TrainingExperiment]
    C --> D[Experiment Results]

    A -->|field<br>features: List[str]<br>target_column: str| A1[default_factory<br>patterns]
    B -->|field<br>hidden_dims: List[int]| B1[mutable default<br>protection]
    C -->|field<br>sort_index: float| C1[custom sort<br>comparison]

    style A fill:#e1f5fe
    style B fill:#f3e5f5
    style C fill:#fff3e0
```

## Real-World AI Engineering Examples

### Example 1: Transformer Model Configuration

```python
from dataclasses import dataclass, field
from typing import List, Optional, Literal
from datetime import datetime

@dataclass
class TransformerConfig:
    vocab_size: int
    d_model: int = 512
    num_heads: int = 8
    num_layers: int = 6
    d_ff: int = 2048
    dropout: float = 0.1
    max_seq_length: int = 512
    activation: Literal["relu", "gelu"] = "gelu"

    # Optional fields with defaults
    positional_encoding: bool = True
    tied_weights: bool = False
    label_smoothing: float = 0.0
    gradient_clip_val: float = 1.0
    mixed_precision: bool = False

    def validate(self) -> bool:
        if self.d_model % self.num_heads != 0:
            return False
        if self.d_ff < self.d_model:
            return False
        return True

@dataclass
class TrainingHyperparameters:
    config: TransformerConfig
    learning_rate: float
    warmup_steps: int
    total_steps: int
    batch_size: int = 32
    weight_decay: float = 0.01
    beta2: float = 0.98
    eps: float = 1e-9

    @property
    def adjusted_lr(self) -> float:
        step = min(self.warmup_steps, self.total_steps)
        return self.learning_rate * step ** 0.5

config = TransformerConfig(vocab_size=30000, num_layers=12)
params = TrainingHyperparameters(
    config=config,
    learning_rate=1e-4,
    warmup_steps=4000,
    total_steps=100000
)
```

### Example 2: Data Augmentation Pipeline

```python
from dataclasses import dataclass, field
from typing import List, Callable, Any
from dataclasses import asdict

@dataclass
class AugmentationConfig:
    name: str
    probability: float
    parameters: dict = field(default_factory=dict)

    def to_transform(self) -> Callable:
        return f"torchvision.transforms.{self.name}"

@dataclass
class AugmentationPipeline:
    image_size: tuple = (224, 224)
    mean: List[float] = field(default_factory=lambda: [0.485, 0.456, 0.406])
    std: List[float] = field(default_factory=lambda: [0.229, 0.224, 0.225])
    augmentations: List[AugmentationConfig] = field(default_factory=list)
    random_seed: int = 42

    def add_augmentation(self, aug: AugmentationConfig) -> None:
        self.augmentations.append(aug)

    def to_dict(self) -> dict:
        return asdict(self)

    def __len__(self) -> int:
        return len(self.augmentations)

pipeline = AugmentationPipeline(
    image_size=(384, 384),
    mean=[0.5, 0.5, 0.5],
    std=[0.5, 0.5, 0.5]
)

pipeline.add_augmentation(AugmentationConfig(
    name="RandomHorizontalFlip",
    probability=0.5
))

pipeline.add_augmentation(AugmentationConfig(
    name="ColorJitter",
    probability=0.8,
    parameters={"brightness": 0.2, "contrast": 0.2}
))
```

## Key Takeaways

| Feature | Use Case |
|---------|----------|
| `frozen=True` | Configuration objects that should not change |
| `default_factory=list` | Mutable fields like lists and dicts |
| `__post_init__()` | Computed fields and validation |
| `order=True` | Sorting dataclass instances |
| `compare=False` | Exclude fields from comparison |

---

**Next file:** [08_02_python_walrus_operator.md](08_02_python_walrus_operator.md)

---

**References:**

- [Python dataclasses documentation](https://docs.python.org/3/library/dataclasses.html)
- [Real Python: Data Classes in Python](https://realpython.com/python-data-classes/)
- [PEP 557 – Data Classes](https://peps.python.org/pep-0557/)
