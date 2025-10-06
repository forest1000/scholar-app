/**
 * LLM Configuration File
 * Configure your Language Model settings here
 */

const LLMConfig = {
    // ===================================
    // Model Selection
    // ===================================
    models: {
        default: 'gpt-4',
        available: [
            {
                id: 'gpt-4',
                name: 'GPT-4',
                provider: 'openai',
                maxTokens: 8192,
                costPer1kTokens: {
                    input: 0.03,
                    output: 0.06
                }
            },
            {
                id: 'gpt-4-turbo',
                name: 'GPT-4 Turbo',
                provider: 'openai',
                maxTokens: 128000,
                costPer1kTokens: {
                    input: 0.01,
                    output: 0.03
                }
            },
            {
                id: 'gpt-3.5-turbo',
                name: 'GPT-3.5 Turbo',
                provider: 'openai',
                maxTokens: 16384,
                costPer1kTokens: {
                    input: 0.0005,
                    output: 0.0015
                }
            },
            {
                id: 'claude-3-opus',
                name: 'Claude 3 Opus',
                provider: 'anthropic',
                maxTokens: 200000,
                costPer1kTokens: {
                    input: 0.015,
                    output: 0.075
                }
            },
            {
                id: 'claude-3-sonnet',
                name: 'Claude 3 Sonnet',
                provider: 'anthropic',
                maxTokens: 200000,
                costPer1kTokens: {
                    input: 0.003,
                    output: 0.015
                }
            },
            {
                id: 'gemini-pro',
                name: 'Gemini Pro',
                provider: 'google',
                maxTokens: 32768,
                costPer1kTokens: {
                    input: 0.00025,
                    output: 0.0005
                }
            }
        ]
    },

    // ===================================
    // API Endpoints
    // ===================================
    endpoints: {
        openai: {
            base: 'https://api.openai.com/v1',
            chat: '/chat/completions',
            embeddings: '/embeddings',
            images: '/images/generations',
            moderation: '/moderations'
        },
        anthropic: {
            base: 'https://api.anthropic.com/v1',
            messages: '/messages',
            complete: '/complete'
        },
        google: {
            base: 'https://generativelanguage.googleapis.com/v1',
            generateContent: '/models/{model}:generateContent'
        },
        custom: {
            base: process.env.CUSTOM_LLM_ENDPOINT || '',
            enabled: false
        }
    },

    // ===================================
    // Generation Parameters
    // ===================================
    parameters: {
        temperature: 0.7,           // 0.0 to 2.0 - Controls randomness
        maxTokens: 2000,           // Maximum tokens in response
        topP: 0.9,                 // 0.0 to 1.0 - Nucleus sampling
        topK: 40,                  // Top-k sampling parameter
        frequencyPenalty: 0.0,     // -2.0 to 2.0 - Reduce repetition
        presencePenalty: 0.0,      // -2.0 to 2.0 - Encourage new topics
        stopSequences: [],         // Array of stop sequences
        stream: false,             // Enable streaming responses
        n: 1,                      // Number of completions to generate
        
        // Response format
        responseFormat: {
            type: 'text',          // 'text' or 'json_object'
            schema: null           // JSON schema if type is 'json_object'
        }
    },

    // ===================================
    // System Prompts
    // ===================================
    systemPrompts: {
        default: "You are a helpful AI assistant. Provide clear, accurate, and helpful responses.",
        
        coding: "You are an expert programmer. Provide clean, efficient, and well-documented code with explanations.",
        
        creative: "You are a creative writing assistant. Help with storytelling, creative ideas, and engaging content.",
        
        academic: "You are an academic assistant. Provide well-researched, cited, and scholarly responses.",
        
        business: "You are a business consultant. Provide professional, strategic, and actionable business advice.",
        
        technical: "You are a technical support specialist. Provide clear technical explanations and troubleshooting help.",
        
        custom: process.env.CUSTOM_SYSTEM_PROMPT || ""
    },

    // ===================================
    // Conversation Management
    // ===================================
    conversation: {
        contextWindow: 10,         // Number of previous messages to include
        maxHistoryTokens: 4000,    // Maximum tokens for conversation history
        summarizeAfter: 20,        // Summarize conversation after N messages
        saveHistory: true,          // Save conversation history
        
        // Memory settings
        memory: {
            enabled: true,
            type: 'short',         // 'short', 'long', or 'both'
            shortTermMessages: 10,  // Last N messages
            longTermSummary: true   // Maintain conversation summary
        }
    },

    // ===================================
    // Safety and Moderation
    // ===================================
    safety: {
        enableModeration: true,
        blockHarmfulContent: true,
        sensitivityLevel: 'medium',  // 'low', 'medium', 'high'
        
        contentFilters: {
            violence: true,
            sexual: true,
            harassment: true,
            hate: true,
            selfHarm: true,
            dangerous: true
        },
        
        // Custom filter words (add your own)
        customBlocklist: [],
        
        // Rate limiting
        rateLimit: {
            enabled: true,
            requestsPerMinute: 60,
            requestsPerHour: 1000,
            requestsPerDay: 10000
        }
    },

    // ===================================
    // Retry and Error Handling
    // ===================================
    retry: {
        maxAttempts: 3,
        initialDelay: 1000,        // milliseconds
        maxDelay: 10000,           // milliseconds
        backoffMultiplier: 2,      // Exponential backoff
        
        // Retry on specific errors
        retryableErrors: [
            'ETIMEDOUT',
            'ECONNRESET',
            'ENOTFOUND',
            'RATE_LIMIT_EXCEEDED',
            '429',
            '503'
        ]
    },

    // ===================================
    // Caching Configuration
    // ===================================
    cache: {
        enabled: true,
        type: 'memory',            // 'memory', 'redis', 'disk'
        ttl: 3600,                 // Time to live in seconds
        maxSize: 100,              // Maximum cache entries
        
        // Cache key generation
        keyStrategy: 'hash',       // 'hash' or 'simple'
        
        // What to cache
        cacheResponses: true,
        cacheEmbeddings: true,
        cacheImages: false
    },

    // ===================================
    // Logging and Monitoring
    // ===================================
    logging: {
        enabled: true,
        level: 'info',             // 'debug', 'info', 'warn', 'error'
        
        // Log destinations
        destinations: {
            console: true,
            file: true,
            database: false,
            external: false         // External logging service
        },
        
        // What to log
        logRequests: true,
        logResponses: true,
        logErrors: true,
        logPerformance: true,
        
        // Privacy settings
        maskSensitiveData: true,
        excludeFields: ['api_key', 'password', 'token']
    },

    // ===================================
    // Performance Optimization
    // ===================================
    performance: {
        // Batching
        batchRequests: false,
        batchSize: 10,
        batchTimeout: 1000,        // milliseconds
        
        // Connection pooling
        connectionPool: {
            enabled: true,
            maxConnections: 10,
            minConnections: 2,
            acquireTimeout: 30000
        },
        
        // Timeout settings
        timeouts: {
            request: 30000,        // milliseconds
            response: 60000,       // milliseconds
            idle: 120000          // milliseconds
        }
    },

    // ===================================
    // Advanced Features
    // ===================================
    features: {
        // Function calling
        functionCalling: {
            enabled: true,
            autoExecute: false,
            maxIterations: 5,
            timeout: 30000
        },
        
        // Embeddings
        embeddings: {
            enabled: true,
            model: 'text-embedding-ada-002',
            dimensions: 1536,
            batchSize: 100
        },
        
        // Image generation
        imageGeneration: {
            enabled: false,
            model: 'dall-e-3',
            defaultSize: '1024x1024',
            quality: 'standard',    // 'standard' or 'hd'
            style: 'natural'        // 'natural' or 'vivid'
        },
        
        // Voice/Audio
        audio: {
            enabled: false,
            tts: {
                model: 'tts-1',
                voice: 'alloy',
                speed: 1.0
            },
            stt: {
                model: 'whisper-1',
                language: 'en'
            }
        },
        
        // Tools and Plugins
        tools: {
            enabled: true,
            available: [
                'web_search',
                'calculator',
                'code_interpreter',
                'image_analyzer'
            ],
            customTools: []
        }
    },

    // ===================================
    // Development Settings
    // ===================================
    development: {
        debug: process.env.NODE_ENV !== 'production',
        mockResponses: false,
        testMode: false,
        verbose: false,
        
        // Development overrides
        overrides: {
            model: process.env.DEV_MODEL || null,
            temperature: process.env.DEV_TEMPERATURE || null,
            maxTokens: process.env.DEV_MAX_TOKENS || null
        }
    },

    // ===================================
    // Utility Functions
    // ===================================
    utils: {
        /**
         * Get model configuration by ID
         */
        getModel: function(modelId) {
            return this.models.available.find(m => m.id === modelId) || null;
        },

        /**
         * Validate API key format
         */
        validateApiKey: function(key, provider) {
            const patterns = {
                openai: /^sk-[a-zA-Z0-9]{48}$/,
                anthropic: /^sk-ant-[a-zA-Z0-9]{95}$/,
                google: /^[a-zA-Z0-9_-]{39}$/
            };
            
            return patterns[provider] ? patterns[provider].test(key) : true;
        },

        /**
         * Calculate token cost
         */
        calculateCost: function(modelId, inputTokens, outputTokens) {
            const model = this.getModel(modelId);
            if (!model) return 0;
            
            const inputCost = (inputTokens / 1000) * model.costPer1kTokens.input;
            const outputCost = (outputTokens / 1000) * model.costPer1kTokens.output;
            
            return {
                input: inputCost,
                output: outputCost,
                total: inputCost + outputCost
            };
        },

        /**
         * Format messages for API
         */
        formatMessages: function(messages, provider) {
            switch(provider) {
                case 'openai':
                    return messages.map(m => ({
                        role: m.role,
                        content: m.content
                    }));
                
                case 'anthropic':
                    return {
                        messages: messages.filter(m => m.role !== 'system'),
                        system: messages.find(m => m.role === 'system')?.content
                    };
                
                case 'google':
                    return {
                        contents: messages.map(m => ({
                            role: m.role === 'assistant' ? 'model' : 'user',
                            parts: [{text: m.content}]
                        }))
                    };
                
                default:
                    return messages;
            }
        },

        /**
         * Sanitize user input
         */
        sanitizeInput: function(text) {
            // Remove control characters
            text = text.replace(/[\x00-\x1F\x7F]/g, '');
            
            // Limit length
            const maxLength = 10000;
            if (text.length > maxLength) {
                text = text.substring(0, maxLength);
            }
            
            return text.trim();
        }
    }
};

// Export for Node.js/CommonJS
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LLMConfig;
}

// Export for ES6 modules
if (typeof exports !== 'undefined') {
    exports.default = LLMConfig;
}

// Make available globally in browser
if (typeof window !== 'undefined') {
    window.LLMConfig = LLMConfig;
}