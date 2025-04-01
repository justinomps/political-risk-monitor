# Enhanced claude.py with objective numerical ratings

import requests
import json
import logging
from config import ANTHROPIC_API_KEY

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('claude')

class ClaudeAPI:
    """
    Handles interactions with the Claude AI API for enhanced text analysis
    with objective ratings and multiple perspectives.
    """
    
    def __init__(self, api_key=None):
        self.api_key = api_key or ANTHROPIC_API_KEY
        if not self.api_key:
            logger.error("No Claude API key provided")
            raise ValueError("Claude API key is required")
            
        # Define different analysis perspectives
        self.perspectives = {
            "neutral": {
                "name": "Neutral Analyst",
                "description": "You are a completely neutral political analyst focused solely on objective facts."
            },
            "conservative": {
                "name": "Conservative Perspective",
                "description": "You are a political analyst with traditional conservative values emphasizing stability, established norms, and cautious interpretation of events."
            },
            "progressive": {
                "name": "Progressive Perspective",
                "description": "You are a political analyst with progressive values emphasizing civil liberties, social justice, and vigilance against potential authoritarian trends."
            }
        }
    
    def analyze_text(self, text, system_prompt=None, max_tokens=1500, model="claude-3-sonnet-20240229"):
        """
        Analyze text using Claude AI.
        
        Args:
            text (str): The main text to analyze
            system_prompt (str, optional): System message to guide Claude
            max_tokens (int): Maximum tokens in response
            model (str): Claude model to use
            
        Returns:
            str or None: Claude's response or None if error
        """
        headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        # Prepare the request payload
        messages = [{"role": "user", "content": text}]
        
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages
        }
        
        # Add system prompt if provided
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            logger.info(f"Sending request to Claude API using model {model}")
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                logger.error(f"Claude API error: Status {response.status_code}, Response: {response.text}")
                return None
            
            result = response.json()
            response_text = result.get('content', [{}])[0].get('text', '')
            
            logger.info(f"Received response from Claude API ({len(response_text)} chars)")
            return response_text
            
        except Exception as e:
            logger.error(f"Error calling Claude API: {str(e)}")
            return None
    
    def _create_analysis_prompt(self, article, categories, perspective_name):
        """Create a specialized prompt for a specific perspective"""
        
        prompt = f"""
        You are analyzing this news article from the perspective of {perspective_name}.
        
        Please analyze according to the Despotism Readiness Framework categories: {', '.join(categories)}
        
        Article Title: {article.get('title', 'No title')}
        
        Article Content:
        {article.get('content', 'No content')}
        
        Source: {article.get('source', 'Unknown')}
        Date: {article.get('published_date', 'Unknown')}
        
        For each category, provide:
        1. A severity rating (GREEN, YELLOW, ORANGE, or RED)
        2. A numerical score from 0-100 where:
           - 0-25: GREEN (No concerning indicators)
           - 26-50: YELLOW (Early warning signs)
           - 51-75: ORANGE (Significant concerns)
           - 76-100: RED (Critical threat)
        3. A brief explanation for your rating
        
        Please respond in JSON format like this:
        {{
            "categories": {{
                "category_id": {{
                    "severity": "severity_level",
                    "score": numerical_score,
                    "explanation": "Your brief explanation"
                }},
                ...
            }},
            "overall_assessment": "Your brief overall assessment"
        }}
        
        Only include the categories I've asked about, and use only GREEN, YELLOW, ORANGE, or RED as severity levels.
        """
        
        return prompt
        
    def analyze_news_article_multi_perspective(self, article, categories, framework_description=None):
        """
        Analyze a news article from multiple perspectives to control for bias.
        
        Args:
            article (dict): Article data with title, content, etc.
            categories (list): List of category IDs to analyze
            framework_description (str, optional): Description of the framework
            
        Returns:
            dict: Combined analysis results with category ratings, scores, and explanations
        """
        all_analyses = {}
        
        # Analyze from each perspective
        for perspective_id, perspective_data in self.perspectives.items():
            # Create system prompt for this perspective
            system_prompt = f"""
            {perspective_data['description']}
            
            Your task is to analyze news articles according to the Despotism Readiness Framework, 
            which tracks indicators of democratic backsliding.
            
            Be thorough and evidence-based in your analysis.
            """
            
            # Add custom framework description if provided
            if framework_description:
                system_prompt += f"\n\n{framework_description}"
                
            # Create the analysis prompt for this perspective    
            prompt = self._create_analysis_prompt(article, categories, perspective_data['name'])
            
            # Call Claude API
            response = self.analyze_text(prompt, system_prompt=system_prompt)
            
            # Parse response
            if response:
                try:
                    # Extract JSON from response
                    json_start = response.find('{')
                    json_end = response.rfind('}') + 1
                    
                    if json_start == -1 or json_end == 0:
                        logger.warning(f"No JSON found in Claude response for {perspective_id} perspective")
                        continue
                    
                    json_str = response[json_start:json_end]
                    result = json.loads(json_str)
                    
                    # Normalize the severity levels to lowercase
                    if 'categories' in result:
                        for cat_id, cat_data in result['categories'].items():
                            if isinstance(cat_data, dict) and 'severity' in cat_data:
                                cat_data['severity'] = cat_data['severity'].lower()
                    
                    # Store this perspective's analysis
                    all_analyses[perspective_id] = result
                    
                except Exception as e:
                    logger.error(f"Error parsing Claude response for {perspective_id} perspective: {str(e)}")
        
        # Combine analyses from all perspectives
        combined_result = self._combine_multi_perspective_analyses(all_analyses)
        return combined_result
            
    def _combine_multi_perspective_analyses(self, all_analyses):
        """
        Combine analyses from multiple perspectives into a single result.
        
        Args:
            all_analyses (dict): Dictionary of analyses by perspective
            
        Returns:
            dict: Combined analysis with averaged scores and all explanations
        """
        if not all_analyses:
            return None
            
        # Initialize combined result
        combined = {
            "categories": {},
            "perspectives": {},
            "overall_assessment": ""
        }
        
        # Get all unique categories across all perspectives
        all_categories = set()
        for perspective_id, analysis in all_analyses.items():
            if 'categories' in analysis:
                all_categories.update(analysis['categories'].keys())
        
        # For each category, combine the results
        for cat_id in all_categories:
            category_combined = {
                "severity": "green",  # Default
                "score": 0,
                "perspective_scores": {},
                "perspective_explanations": {}
            }
            
            scores = []
            severities = []
            
            # Collect data from each perspective
            for perspective_id, analysis in all_analyses.items():
                if 'categories' in analysis and cat_id in analysis['categories']:
                    cat_data = analysis['categories'][cat_id]
                    
                    # Store perspective-specific data
                    if isinstance(cat_data, dict):
                        if 'score' in cat_data:
                            score = cat_data['score']
                            scores.append(score)
                            category_combined["perspective_scores"][perspective_id] = score
                            
                        if 'severity' in cat_data:
                            severities.append(cat_data['severity'])
                            
                        if 'explanation' in cat_data:
                            category_combined["perspective_explanations"][perspective_id] = cat_data['explanation']
            
            # Calculate average score if we have any
            if scores:
                avg_score = sum(scores) / len(scores)
                category_combined["score"] = round(avg_score, 1)
                
                # Determine severity based on average score
                if avg_score <= 25:
                    category_combined["severity"] = "green"
                elif avg_score <= 50:
                    category_combined["severity"] = "yellow"
                elif avg_score <= 75:
                    category_combined["severity"] = "orange"
                else:
                    category_combined["severity"] = "red"
            
            # Store combined category data
            combined["categories"][cat_id] = category_combined
        
        # Store the raw perspective analyses
        for perspective_id, analysis in all_analyses.items():
            if 'overall_assessment' in analysis:
                combined["perspectives"][perspective_id] = {
                    "overall_assessment": analysis["overall_assessment"]
                }
        
        # Create a combined overall assessment
        assessment_parts = []
        for perspective_id, analysis in all_analyses.items():
            if 'overall_assessment' in analysis:
                assessment_parts.append(f"{self.perspectives[perspective_id]['name']}: {analysis['overall_assessment']}")
        
        combined["overall_assessment"] = " | ".join(assessment_parts)
        
        return combined


# For testing
if __name__ == "__main__":
    claude_api = ClaudeAPI()
    test_response = claude_api.analyze_text("Hello, Claude. What's the weather like today?")
    print(test_response)