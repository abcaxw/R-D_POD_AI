# Enhanced RnD Assistant

A sophisticated multi-agent RAG (Retrieval-Augmented Generation) system for R&D analysis with image URL support and smart search capabilities.

## 🚀 Features

### Core Analysis Types
- **📊 Benchmark Analysis** - Competitor analysis and winning/losing product identification
- **🕳️ Market Gap Discovery** - Identify untapped market opportunities
- **✅ Idea Verification** - Validate business concepts with market data
- **📈 Audience Volume Estimation** - Estimate potential customer base size
- **🔍 Smart Search** - Intelligent product search with image support

### Smart Search Capabilities
- **Text → Image**: Find product images based on text descriptions
- **Image → Image**: Find similar products using image input
- **Image → Text**: Describe and analyze uploaded images
- **Text → Text**: Traditional text-based product search

## 🏗️ Architecture

```
enhanced_rnd_assistant/
├── config/                 # Configuration settings
├── database/              # Milvus vector database management
├── agents/                # Individual analysis agents
├── tools/                 # Search and utility tools
├── workflow/              # LangGraph workflow orchestration
├── utils/                 # Helper functions and utilities
├── interface/             # User interface and chatbot
└── main.py               # Entry point
```

## 📦 Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd enhanced_rnd_assistant
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**
```bash
# Create .env file
OPENAI_API_KEY=your_openai_api_key
MILVUS_HOST=10.10.10.140
MILVUS_PORT=19530
COLLECTION_NAME=product_collection
```

4. **Configure Milvus**
- Ensure Milvus server is running
- Collection should contain product data with fields:
  - `id_sanpham`, `description`, `metadata`, `date`, `image`
  - `like`, `comment`, `share`, `platform`, `name_store`
  - `description_vector`, `image_vector` (optional)

## 🚀 Usage

### Interactive Mode (Default)
```bash
python main.py
# or
python main.py interactive
```

### Available Commands
```bash
python main.py test        # Run system tests
python main.py batch       # Run batch processing test
python main.py async       # Run async interactive mode
```

### Example Queries

#### Benchmark Analysis
```
"Phân tích benchmark các sản phẩm keychain Star Wars cho Dad audience"
```

#### Market Gap Analysis
```
"Tìm market gap trong segment personalized gifts cho Father's Day"
```

#### Idea Verification
```
"Verify ý tưởng làm custom keychain với Darth Vader theme và LED light"
```

#### Audience Volume Estimation
```
"Estimate audience volume cho Star Wars merchandise trên các social platforms"
```

#### Smart Search
```
"Tìm hình ảnh các sản phẩm keychain đẹp nhất"
"Show me images of trending personalized Dad gifts"
```

### Interactive Commands
- `image:[path]` - Load image from file path
- `debug` - Toggle debug mode
- `quit` - Exit the application

## 🔧 Configuration

### Main Configuration (config/settings.py)
- Milvus connection settings
- OpenAI model configurations
- Search parameters
- Analysis thresholds

### Environment Variables
```bash
MILVUS_HOST=10.10.10.140
MILVUS_PORT=19530
COLLECTION_NAME=product_collection
OPENAI_MODEL=gpt-4
VISION_MODEL=gpt-4-vision-preview
EMBEDDING_MODEL=text-embedding-ada-002
TOP_K=10
```

## 🏛️ Agent Architecture

### Base Agent
- Common functionality for all agents
- Engagement score calculation
- Safe data conversion utilities

### Specialized Agents
- **Query Classifier**: Determines query type and routing
- **Search Agent**: Handles product search with filters
- **Smart Search Agent**: Image-aware search capabilities
- **Analysis Agents**: Benchmark, Market Gap, Idea Verification, Audience Volume
- **Response Generator**: Creates formatted responses

## 📊 Data Flow

1. **Query Classification** → Determine analysis type
2. **Search Execution** → Find relevant products
3. **Analysis Processing** → Apply specialized analysis
4. **Response Generation** → Format final answer

## 🔍 Search Features

### Vector Search
- Text embedding with OpenAI models
- Cosine similarity matching
- Filtered search with expressions

### Image Support
- Base64 image encoding
- CLIP model integration (placeholder)
- Image-to-text description
- Visual similarity search

## 📈 Analysis Capabilities

### Engagement Analysis
- Like, comment, share metrics
- Platform-specific weighting
- Trend analysis over time

### Market Intelligence
- Competitor performance comparison
- Gap identification algorithms
- Audience volume estimation
- Success factor extraction

## 🛠️ Development

### Adding New Agents
1. Inherit from `BaseAgent`
2. Implement `process()` method
3. Add to workflow routing
4. Update response generator

### Adding New Tools
1. Create tool in `tools/` directory
2. Use `@tool` decorator
3. Import in workflow components

### Testing
```bash
# Run system tests
python main.py test

# Run specific test
pytest tests/test_agents.py
```

## 🔒 Security Considerations

- API keys stored in environment variables
- Input validation for image uploads
- Safe error handling throughout

## 📝 API Usage

### Programmatic Access
```python
from interface.chatbot import RnDChatbot

chatbot = RnDChatbot()
response = await chatbot.chat("Your query here")
print(response)
```

### Batch Processing
```python
queries = ["Query 1", "Query 2", "Query 3"]
results = await chatbot.batch_process(queries)
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For issues and questions:
1. Check the documentation
2. Review example queries
3. Enable debug mode for troubleshooting
4. Check Milvus connection and data

## 🔄 Updates

### Version 2.0 Features
- ✅ Single collection architecture
- ✅ Image URL support
- ✅ Smart search capabilities
- ✅ Enhanced response formatting
- ✅ Debug mode
- ✅ Batch processing

### Planned Features
- CLIP model integration
- Advanced filtering options
- Real-time data updates
- Web interface
- API endpoints