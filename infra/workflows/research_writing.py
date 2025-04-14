

class ResearchReportWorkflow:
    def __init__():
        workflow = {}
        workflow.add(planner_agent)
        workflow.add(research_supervisor)
        workflow.add(syntheziser_agent)
        workflow.add(writing_supervisor)

        workflow.add_edge(START, planner_agent)
        workflow.add_edge(planner_agent, research_supervisor, "one-to-many")
        workflow.add_edge(planner_agent, syntheziser)
        workflow.add_edge(research_supervisor, syntheziser)
        workflow.add_edge(syntheziser, writing_supervisor)
        workflow.add_edge(writing_supervisor, END)
