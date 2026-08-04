from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
from seo_agents.crew import Article, ArticleOutline, OptimizedElements

@CrewBase
class MultiContentCrew:
    agents_config = "config/multi_agents.yaml"
    tasks_config = "config/multi_tasks.yaml"

    @agent
    def content_analyzer(self) -> Agent:
        return Agent(
            config=self.agents_config['content_analyzer'],
            verbose=True,
        )

    # @agent
    # def outline_creator(self) -> Agent:
    #     return Agent(
    #         config=self.agents_config['outline_creator'],
    #         verbose=True,
    #     )
    @agent
    def content_outline_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['content_outline_researcher'],
            verbose=True,
        )

    @agent
    def seo_content_optimizer(self) -> Agent:
        return Agent(
            config=self.agents_config['seo_content_optimizer'],
            verbose=True,
        )



    @agent
    def seo_content_writer(self) -> Agent:
        return Agent(
            config=self.agents_config['seo_content_writer'],
            verbose=True,
        )

    @agent
    def seo_content_reviewer(self) -> Agent:
        return Agent(
            config=self.agents_config['seo_content_reviewer'],
            verbose=True,
        )

    @agent
    def seo_content_rewriter(self) -> Agent:
        return Agent(
            config=self.agents_config['seo_content_rewriter'],
            verbose=True,
        )

    @agent
    def content_visualizer(self) -> Agent:
        return Agent(
            config=self.agents_config['content_visualizer'],
            verbose=True,
        )

    @task
    def extract_outline_task(self) -> Task:
        return Task(
            config=self.tasks_config['extract_outline_task'],
        )

    @task
    def generate_outline_task(self) -> Task:
        return Task(
            config=self.tasks_config['generate_outline_task'],
        )

    @task
    def improve_seo_elements_task(self) -> Task:
        return Task(
            config=self.tasks_config['improve_seo_elements_task'],
            output_json=OptimizedElements
        )

    @task
    def write_article_task(self) -> Task:
        return Task(
            config=self.tasks_config['write_article_task'],
        )

    @task
    def rewrite_article_task(self) -> Task:
        return Task(
            config=self.tasks_config['rewrite_article_task'],
        )

    @task
    def trim_article_task(self) -> Task:
        return Task(
            config=self.tasks_config['trim_article_task'],
        )

    @task
    def generate_image_prompts_task(self) -> Task:
        return Task(
            config=self.tasks_config['generate_image_prompts_task'],
        )

    # Crew methods mirroring ContentAnalyzerCrew
    def outline_extraction_crew(self) -> Crew:
        """Crew for generating the content outline"""
        return Crew(
            agents=[self.content_analyzer()],
            tasks=[self.extract_outline_task()],
            process=Process.sequential,
            verbose=True
        )

    def outline_generation_crew(self) -> Crew:
        """Crew for generating the outline using top articles analysis"""
        return Crew(
            agents=[self.content_outline_researcher()],
            tasks=[self.generate_outline_task()],
            process=Process.sequential,
            verbose=True
        )

    def seo_content_optimization_crew(self) -> Crew:
        """Crew for optimizing SEO elements"""
        return Crew(
            agents=[self.seo_content_optimizer()],
            tasks=[self.improve_seo_elements_task()],
            process=Process.sequential,
            verbose=True
        )

    def seo_writer_crew(self) -> Crew:
        """Crew for optimizing SEO elements"""
        print('NAT seo_writer_crew: ', self.seo_content_writer())
        return Crew(
            agents=[self.seo_content_writer()],
            tasks=[self.write_article_task()],
            process=Process.sequential,
            verbose=True
        )

    def seo_rewriter_crew(self) -> Crew:
        """Crew for rewriting content based on SEO feedback"""
        return Crew(
            agents=[self.seo_content_rewriter()],
            tasks=[self.rewrite_article_task()],
            process=Process.sequential,
            verbose=True
        )

    def trim_article_crew(self) -> Crew:
        """Crew for condensing an article down to a target word count"""
        return Crew(
            agents=[self.seo_content_rewriter()],
            tasks=[self.trim_article_task()],
            process=Process.sequential,
            verbose=True
        )

    def image_prompts_crew(self) -> Crew:
        """Crew for generating image prompts"""
        return Crew(
            agents=[self.content_visualizer()],
            tasks=[self.generate_image_prompts_task()],
            process=Process.sequential,
            verbose=True
        )

    
