import logging
from uuid import UUID
from http import HTTPStatus
from typing import Union, List

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers import SchedulerAlreadyRunningError, SchedulerNotRunningError

from api.server.utils.problems import InvalidInputException
from api.server.scheduler import get_scheduler
from api.server.db import get_mongo_c, get_mongo_d
from api.server.db.workflow import WorkflowModel
from api.server.db.scheduledtasks import ScheduledTask, SchedulerStatus, SchedulerStatusResp
from common import mongo_helpers

logger = logging.getLogger(__name__)
router = APIRouter()


async def check_workflows_exist(workflow_col: AsyncIOMotorCollection, task: ScheduledTask):
    workflow: WorkflowModel
    for workflow in task.workflows:
        if not await mongo_helpers.count_items(workflow_col, query={"id_": workflow.id_}):
            raise InvalidInputException("create", "ScheduledTask", task.name,
                                        errors={"error": f"{workflow.id_} does not exist"})

def construct_trigger(trigger_args):
    trigger_type = trigger_args['type']
    trigger_args = trigger_args['args']
    try:
        if trigger_type == 'date':
            return DateTrigger(**trigger_args)
        elif trigger_type == 'interval':
            return IntervalTrigger(**trigger_args)
        elif trigger_type == 'cron':
            return CronTrigger(**trigger_args)
        else:
            raise InvalidTriggerArgs(
                'Invalid scheduler type {0} with args {1}.'.format(trigger_type, trigger_args))
    except (KeyError, ValueError, TypeError):
        raise InvalidTriggerArgs('Invalid scheduler arguments')


@router.get("/",
            response_model=SchedulerStatusResp, response_description="Current scheduler status in WALKOFF.")
async def get_scheduler_status(*, scheduler: AsyncIOScheduler = Depends(get_scheduler)):
    return SchedulerStatusResp(status=scheduler.state)


@router.put("/",
            response_model=SchedulerStatus, response_description="The updated scheduler status in WALKOFF.")
async def update_scheduler_status(*, scheduler: AsyncIOScheduler = Depends(get_scheduler),
                                  new_state: SchedulerStatus):
    try:
        if new_state == "start":
            scheduler.start()
        elif new_state == "stop":
            scheduler.shutdown()
        elif new_state == "pause":
            scheduler.pause()
        elif new_state == "resume":
            scheduler.resume()
    except SchedulerAlreadyRunningError:
        raise InvalidInputException(new_state, "Scheduler", "", errors={"error": "Scheduler already running."})
    except SchedulerNotRunningError:
        raise InvalidInputException(new_state, "Scheduler", "", errors={"error": "Scheduler is not running."})
    return SchedulerStatusResp(status=scheduler.state)


@router.get("/tasks")
async def read_all_scheduled_tasks(*, task_col: AsyncIOMotorCollection = Depends(get_mongo_c),
                                   page: int = 1,
                                   num_per_page: int = 20):
    return await mongo_helpers.get_all_items(task_col, ScheduledTask, page=page, num_per_page=num_per_page)
    # page = request.args.get('page', 1, type=int)
    # return [task.as_json() for task in
    #         ScheduledTask.query.paginate(page, current_app.config['ITEMS_PER_PAGE'], False).items], HTTPStatus.OK


@router.post("/tasks")
async def create_scheduled_task(*, walkoff_db: AsyncIOMotorDatabase = Depends(get_mongo_d),
                                new_task: ScheduledTask):
    task_col = walkoff_db.tasks
    workflow_col = walkoff_db.workflows

    await check_workflows_exist(workflow_col, new_task)
    await mongo_helpers.create_item(task_col, ScheduledTask, new_task)
    # data = request.get_json()
    # invalid_uuids = validate_uuids(data['workflows'])
    # if invalid_uuids:
    #     return invalid_uuid_problem(invalid_uuids)
    # task = ScheduledTask.query.filter_by(name=data['name']).first()
    # if task is None:
    #     try:
    #         task = ScheduledTask(**data)
    #     except InvalidTriggerArgs:
    #         return invalid_scheduler_args_problem
    #     else:
    #         db.session.add(task)
    #         db.session.commit()
    #         return task.as_json(), HTTPStatus.CREATED
    # else:
    #     return scheduled_task_name_already_exists_problem(data['name'], 'create')


@router.get("/tasks/{task_id}")
async def read_scheduled_task(*, task_col: AsyncIOMotorCollection = Depends(get_mongo_c),
                              task_id: Union[UUID, str]):
    return await mongo_helpers.get_item(task_col, ScheduledTask, task_id)


@router.post("/tasks/{task_id}")
async def control_scheduled_task(*, task_col: AsyncIOMotorCollection = Depends(get_mongo_c),
                                 task_id: Union[UUID, str],
                                 new_status: SchedulerStatus):

    if new_status == 'start':
        scheduled_task_id.start()
    elif action == 'stop':
        scheduled_task_id.stop()
    db.session.commit()
    return {}, HTTPStatus.OK


@router.put("/tasks/{task_id}")
async def update_scheduled_task(*, walkoff_db: AsyncIOMotorDatabase = Depends(get_mongo_d),
                                task_id: Union[UUID, str],
                                new_task: ScheduledTask):
    task_col = walkoff_db.tasks
    workflow_col = walkoff_db.workflows

    await check_workflows_exist(workflow_col, new_task)
    return await mongo_helpers.update_item(task_col, ScheduledTask, task_id, new_task)
    #
    # data = request.get_json()
    # invalid_uuids = validate_uuids(data.get('workflows', []))
    # if invalid_uuids:
    #     return invalid_uuid_problem(invalid_uuids)
    # if 'name' in data:
    #     same_name = ScheduledTask.query.filter_by(name=data['name']).first()
    #     if same_name is not None and same_name.id != data['id']:
    #         return scheduled_task_name_already_exists_problem(same_name, 'update')
    # try:
    #     scheduled_task_id.update(data)
    # except InvalidTriggerArgs:
    #     return invalid_scheduler_args_problem
    # else:
    #     db.session.commit()
    #     return scheduled_task_id.as_json(), HTTPStatus.OK


@router.delete("/tasks/{task_id}")
async def delete_scheduled_task(*, task_col: AsyncIOMotorCollection = Depends(get_mongo_c),
                                task_id: Union[UUID, str]):
    return await mongo_helpers.delete_item(task_col, ScheduledTask, task_id)
