"""
Financial Modeling API Endpoints
------------------------------

This module provides API endpoints for AI-driven financial modeling.

What this file does:
1. Exposes endpoints for generating AI-powered financial models
2. Handles parameter parsing for modeling options
3. Coordinates between the financial data aggregator and AI modeler
4. Serves financial model results via FastAPI's response system

How it fits in the architecture:
- Part of the API layer, providing financial modeling functionality
- Consumes data from financial_data_aggregator service
- Uses ai_financial_modeler service to generate models
- Provides an interface for frontend financial analysis requests
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.ai_financial_modeler import ai_financial_modeler
from app.services.financial_data_aggregator import financial_data_aggregator


# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


# Request/response models
class ModelingRequest(BaseModel):
    """Request model for financial modeling."""

    ticker: str
    years_historical: int = 5
    years_projection: int = 5
    include_quarterly: bool = True


class ModelingResponse(BaseModel):
    """Response model for financial modeling."""

    ticker: str
    metadata: Dict[str, Any]
    historical_analysis: str
    assumptions: Dict[str, Any]
    projections: Dict[str, Any]
    valuation: Dict[str, Any]
    risk_factors: List[Dict[str, str]]


class ModelJobResponse(BaseModel):
    """Response model for async modeling job."""

    job_id: str
    ticker: str
    status: str
    estimated_completion_time: Optional[datetime] = None


# Background task storage
modeling_jobs = {}


@router.post(
    "/model", response_model=ModelingResponse, summary="Generate financial model"
)
async def generate_financial_model(request: ModelingRequest):
    """
    Generate a comprehensive AI-driven financial model.

    This endpoint:
    1. Retrieves historical financial data for the company
    2. Uses AI to analyze accounting policies and financial trends
    3. Generates a complete financial model with projections
    4. Returns the model as a JSON response

    Parameters:
    - **ticker**: Stock symbol of the company (e.g., AAPL, MSFT)
    - **years_historical**: Number of years of historical data to include (default: 5)
    - **years_projection**: Number of years to project forward (default: 5)
    - **include_quarterly**: Whether to include quarterly data (default: true)

    Returns:
    - Complete financial model with projections and analysis
    """
    logger.info(f"Generating financial model for {request.ticker}")

    try:
        # Build the financial model
        financial_model = ai_financial_modeler.build_financial_model(
            ticker=request.ticker,
            years_historical=request.years_historical,
            years_projection=request.years_projection,
            include_quarterly=request.include_quarterly,
        )

        # Convert the model to the response format
        response = ModelingResponse(
            ticker=request.ticker,
            metadata=financial_model.get("metadata", {}),
            historical_analysis=financial_model.get("historical_analysis", ""),
            assumptions=financial_model.get("assumptions", {}),
            projections=financial_model.get("projections", {}),
            valuation=financial_model.get("valuation", {}),
            risk_factors=financial_model.get("risk_factors", []),
        )

        return response

    except Exception as e:
        logger.error(f"Error generating financial model: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to generate financial model: {str(e)}"
        )


@router.post(
    "/model/async",
    response_model=ModelJobResponse,
    summary="Generate financial model asynchronously",
)
async def generate_financial_model_async(
    request: ModelingRequest, background_tasks: BackgroundTasks
):
    """
    Start an asynchronous financial modeling job.

    This endpoint:
    1. Starts a background task to generate a financial model
    2. Returns a job ID that can be used to check the status or retrieve results
    3. Processes the model generation without blocking the API

    Parameters:
    - Same as /model endpoint

    Returns:
    - Job information including ID and status
    """
    logger.info(f"Starting async financial modeling job for {request.ticker}")

    try:
        # Generate a job ID
        import uuid

        job_id = str(uuid.uuid4())

        # Create job entry
        modeling_jobs[job_id] = {
            "ticker": request.ticker,
            "status": "pending",
            "created_at": datetime.now(),
            "estimated_completion_time": datetime.now().timestamp()
            + 300,  # Estimate 5 minutes
            "result": None,
        }

        # Add the background task
        background_tasks.add_task(
            process_modeling_job,
            job_id,
            request.ticker,
            request.years_historical,
            request.years_projection,
            request.include_quarterly,
        )

        # Return the job information
        return ModelJobResponse(
            job_id=job_id,
            ticker=request.ticker,
            status="pending",
            estimated_completion_time=datetime.fromtimestamp(
                modeling_jobs[job_id]["estimated_completion_time"]
            ),
        )

    except Exception as e:
        logger.error(f"Error starting modeling job: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to start modeling job: {str(e)}"
        )


@router.get("/model/job/{job_id}", summary="Get modeling job status")
async def get_modeling_job_status(job_id: str):
    """
    Check the status of an asynchronous modeling job.

    This endpoint:
    1. Retrieves the current status of a modeling job
    2. Returns the results if the job is complete

    Parameters:
    - **job_id**: The ID of the job to check

    Returns:
    - Job status and results if complete
    """
    logger.info(f"Checking status for modeling job {job_id}")

    try:
        # Check if the job exists
        if job_id not in modeling_jobs:
            raise HTTPException(
                status_code=404, detail=f"Modeling job {job_id} not found"
            )

        job = modeling_jobs[job_id]

        # If the job is complete, return the results
        if job["status"] == "completed":
            return {
                "job_id": job_id,
                "ticker": job["ticker"],
                "status": "completed",
                "completed_at": job.get("completed_at"),
                "result": job["result"],
            }

        # If the job failed, return the error
        if job["status"] == "failed":
            return {
                "job_id": job_id,
                "ticker": job["ticker"],
                "status": "failed",
                "error": job.get("error"),
                "failed_at": job.get("failed_at"),
            }

        # If the job is still pending, return the status
        return {
            "job_id": job_id,
            "ticker": job["ticker"],
            "status": "pending",
            "created_at": job["created_at"],
            "estimated_completion_time": datetime.fromtimestamp(
                job["estimated_completion_time"]
            ),
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error checking job status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to check job status: {str(e)}"
        )


async def process_modeling_job(
    job_id: str,
    ticker: str,
    years_historical: int,
    years_projection: int,
    include_quarterly: bool,
):
    """
    Process a financial modeling job in the background.

    Args:
        job_id: Job ID
        ticker: Company ticker symbol
        years_historical: Number of years of historical data
        years_projection: Number of years to project
        include_quarterly: Whether to include quarterly data
    """
    try:
        # Build the financial model
        financial_model = ai_financial_modeler.build_financial_model(
            ticker=ticker,
            years_historical=years_historical,
            years_projection=years_projection,
            include_quarterly=include_quarterly,
        )

        # Update the job with the results
        modeling_jobs[job_id]["status"] = "completed"
        modeling_jobs[job_id]["completed_at"] = datetime.now()
        modeling_jobs[job_id]["result"] = financial_model

        logger.info(f"Completed financial modeling job {job_id} for {ticker}")

    except Exception as e:
        logger.error(f"Error processing modeling job {job_id}: {e}", exc_info=True)

        # Update the job with the error
        modeling_jobs[job_id]["status"] = "failed"
        modeling_jobs[job_id]["failed_at"] = datetime.now()
        modeling_jobs[job_id]["error"] = str(e)


@router.get("/{symbol}/quick-model", summary="Get quick financial model summary")
async def get_quick_model(
    symbol: str, years: int = Query(3, description="Years of historical data")
):
    """
    Generate a quick summary financial model.

    This endpoint:
    1. Retrieves key financial data for the company
    2. Generates a simplified financial model with basic projections
    3. Returns a concise summary suitable for dashboard display

    Parameters:
    - **symbol**: Stock symbol of the company (e.g., AAPL, MSFT)
    - **years**: Number of years of historical data (default: 3)

    Returns:
    - Simplified financial model summary
    """
    logger.info(f"Generating quick model for {symbol}")

    try:
        # Get financial data
        financial_data = financial_data_aggregator.get_comprehensive_financial_data(
            ticker=symbol, years=years, include_quarterly=False
        )

        if not financial_data or not financial_data.get("annual_data"):
            raise HTTPException(
                status_code=404,
                detail=f"Insufficient financial data available for {symbol}",
            )

        # Generate a quick model summary
        # In a production system, this would be more sophisticated
        summary = {}

        # Get historical revenue and growth
        if (
            "time_series" in financial_data
            and "annual" in financial_data["time_series"]
        ):
            time_series = financial_data["time_series"]["annual"]

            if "Revenue" in time_series:
                # Extract revenue data
                revenue_data = time_series["Revenue"]
                summary["historical_revenue"] = revenue_data

                # Calculate growth rates if we have enough data
                if len(revenue_data) >= 2:
                    growth_rates = []
                    for i in range(1, len(revenue_data)):
                        current = revenue_data[i]["value"]
                        previous = revenue_data[i - 1]["value"]
                        if previous and current:
                            growth_rate = (current - previous) / previous * 100
                            growth_rates.append(
                                {
                                    "year": revenue_data[i]["year"],
                                    "growth_rate": growth_rate,
                                }
                            )

                    summary["historical_growth_rates"] = growth_rates

                    # Project forward using average growth rate
                    if growth_rates:
                        avg_growth_rate = sum(
                            g["growth_rate"] for g in growth_rates
                        ) / len(growth_rates)
                        last_revenue = revenue_data[-1]["value"]
                        last_year = int(revenue_data[-1]["year"])

                        projected_revenue = []
                        for i in range(1, 4):  # Project 3 years forward
                            year = last_year + i
                            revenue = last_revenue * (1 + avg_growth_rate / 100) ** i
                            projected_revenue.append(
                                {"year": str(year), "projected_revenue": revenue}
                            )

                        summary["projected_revenue"] = projected_revenue
                        summary["assumed_growth_rate"] = avg_growth_rate

        return summary

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error generating quick model: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to generate quick model: {str(e)}"
        )
