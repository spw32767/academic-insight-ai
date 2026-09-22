"""Seven-category taxonomy used by local examples and Scopus export tests."""

from academic_insight_ai.tasks.article_classification.service import CategoryDefinition


CATEGORIES = [
    CategoryDefinition(code="THEORETICAL_CS", name="Theoretical Computer Science", description="Mathematical foundations of computation, algorithm design, complexity, formal reasoning, formal verification, model checking, semantics, and computability."),
    CategoryDefinition(code="AI_ALGORITHMS", name="AI Algorithms and Intelligent Systems", description="New AI or machine-learning algorithms, optimization methods, intelligent models, learning architectures, generative AI, explainable AI, and multimodal learning."),
    CategoryDefinition(code="APPLIED_AI", name="Applied AI, GeoAI and Agentic Applications", description="Applications of established AI to real-world domains, autonomous agents, GeoAI, decision support, healthcare, agriculture, smart cities, GIS, remote sensing, and operational systems."),
    CategoryDefinition(code="NETWORKS_SECURITY_DISTRIBUTED", name="Networks, Security, and Distributed Systems", description="Networking, cybersecurity, distributed systems, cloud-edge architectures, blockchain, authentication, encryption, routing, protocols, latency, and throughput."),
    CategoryDefinition(code="QUANTUM_INFORMATION", name="Quantum Information Science", description="Quantum computing, communication, cryptography, algorithms, circuits, qubits, quantum machine learning, simulation, networking, and post-quantum cryptography."),
    CategoryDefinition(code="COMPUTER_ENGINEERING_IOT_EMBEDDED", name="Computer Engineering, IoT, and Embedded Systems", description="Hardware-oriented systems, embedded platforms, IoT devices, sensors, robotics, cyber-physical systems, firmware, FPGA, and hardware acceleration."),
    CategoryDefinition(code="EDTECH_LEARNING_DIGITAL_LIBRARY", name="Educational Technology, Learning Sciences, and Digital Library Systems", description="Education, learning environments, learning analytics, intelligent tutoring, educational data mining, digital libraries, academic information systems, and information literacy."),
]
