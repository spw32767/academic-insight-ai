"""Frozen Astra v1 development examples for the opt-in prompt experiment."""

EXAMPLES = (
    ("SCOPUS_ID:105034621120", "LLM-guided population-based reinforcement learning",
     "language-model reasoning directly inside the selection-mutation stage of training",
     "AI_ALGORITHMS", "The training method itself is the contribution."),
    ("SCOPUS_ID:105041610874", "Improved Teaching-Learning-Based Optimization Algorithm",
     "a hybrid crossover framework combining a multi-parent crossover operator with an adaptive crossover mechanism",
     "AI_ALGORITHMS", "The work changes a reusable optimization algorithm."),
    ("SCOPUS_ID:105028884620", "XcepFusion for brain tumor detection",
     "combining deep learning feature extraction with standard machine learning classifiers",
     "APPLIED_AI", "The main result is disease detection using existing learning techniques."),
    ("SCOPUS_ID:105036815463", "Thai restaurant aspect-based sentiment analysis using transfer learning",
     "We fine-tune multiple pretrained BERT-based models",
     "APPLIED_AI", "The main result is a specific language task, not a general learning method."),
    ("SCOPUS_ID:105049712190", "Energy-efficient underwater sensor network protocol",
     "a novel energy-efficient routing protocol for UWSNs",
     "NETWORKS_SECURITY_DISTRIBUTED", "Routing and communication are the main system contribution."),
    ("SCOPUS_ID:105009698319", "Information-centric IoT caching using reinforcement learning",
     "optimize caching decisions in ICN-IoT environments",
     "NETWORKS_SECURITY_DISTRIBUTED", "Learning is a tool for a network caching problem."),
    ("SCOPUS_ID:105040835421", "Multiplierless decimation filter for wireless applications",
     "The decimation filter has been built on Xilinx Kintex 7 Field Programmable Gate Array",
     "COMPUTER_ENGINEERING_IOT_EMBEDDED", "The implemented hardware filter is the contribution."),
    ("SCOPUS_ID:85211045919", "Retraction Notice to a physics article",
     "This article has been retracted",
     None, "A retraction notice has no research contribution; use Preface."),
)

EXAMPLE_IDS = frozenset(example[0] for example in EXAMPLES)

# Version 2 keeps the same number of examples but contrasts architectural novelty
# with adapting an existing model inside the same application domains.
BOUNDARY_EXAMPLES = (
    ("SCOPUS_ID:105031524974", "LymphAware lymphoma diagnosis",
     "adversarial and orthogonality-based shortcut suppression",
     "AI_ALGORITHMS", "A new bias-control learning mechanism is the main contribution, even in healthcare."),
    ("SCOPUS_ID:105031135975", "KANU-Net colorectal polyp segmentation",
     "Our method introduces pixel-level radial basis function (RBF) lifting",
     "AI_ALGORITHMS", "A new representation mechanism changes the model architecture, despite the medical task."),
    ("SCOPUS_ID:105034653036", "KNN and Grey Wolf Optimizer for breast cancer classification",
     "GWO autonomously identifies the most informative features and determines the optimal KNN parameter settings",
     "APPLIED_AI", "An existing optimizer tunes an existing classifier for a specific diagnosis task."),
    ("SCOPUS_ID:105032735288", "Thai elderly speech recognition using transfer learning",
     "applies transfer learning to the Wav2Vec2-large-xlsr-53-Th model",
     "APPLIED_AI", "An existing model is adapted to a specific speech-recognition task."),
    *EXAMPLES[4:],
)

BOUNDARY_EXAMPLE_IDS = frozenset(example[0] for example in BOUNDARY_EXAMPLES)
