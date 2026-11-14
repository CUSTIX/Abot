"""Writes and rules for the pay schedule, bills and the payday split."""

import datetime as dt
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction as db_transaction

from money import services as money
from planning import cycle
from planning.models import (
    Bill,
    BillPayment,
    Goal,
    PaydaySplit,
    PaySchedule,
    SplitLine,
    SplitRule,
)


def schedule_for(owner) -> PaySchedule:
    schedule, _ = PaySchedule.objects.get_or_create(owner=owner)
    return schedule


def save_schedule(schedule: PaySchedule) -> PaySchedule:
    if schedule.frequency == cycle.SEMI_MONTHLY and schedule.first_day == schedule.second_day:
        raise ValidationError({"second_day": "Pick two different days."})
    schedule.save()
    return schedule


def _check_owner(owner, *objects) -> None:
    for obj in objects:
        if obj is not None and obj.owner_id != owner.pk:
            raise ValidationError("Not found.")


def save_bill(bill: Bill) -> Bill:
    _check_owner(bill.owner, bill.wallet, bill.category)
    if bill.category is not None and bill.category.kind != "expense":
        raise ValidationError({"category": "Pick an expense category."})
    if Bill.objects.filter(owner=bill.owner, name__iexact=bill.name).exclude(pk=bill.pk).exists():
        raise ValidationError({"name": "You already have a bill with that name."})
    bill.save()
    return bill


@db_transaction.atomic
def pay_bill(
    bill: Bill, *, due_date: dt.date, paid_on: dt.date, amount: Decimal | None = None, wallet=None
) -> BillPayment:
    """Record the expense that pays one due date of a bill, and mark that due date paid."""
    if due_date not in cycle.bill_due_dates(bill.due_day, due_date, due_date):
        when = f"{due_date:%b} {due_date.day}"
        raise ValidationError({"due_date": f"{bill.name} isn't due on {when}."})
    if BillPayment.objects.filter(bill=bill, due_date=due_date).exists():
        raise ValidationError({"due_date": "That bill is already marked paid."})
    txn = money.record(
        owner=bill.owner,
        kind="expense",
        amount=amount or bill.amount,
        date=paid_on,
        wallet=wallet or bill.wallet,
        category=bill.category,
        note=bill.name,
    )
    try:
        with db_transaction.atomic():
            return BillPayment.objects.create(bill=bill, due_date=due_date, transaction=txn)
    except IntegrityError as exc:  # paid twice at the same moment (double tap)
        raise ValidationError({"due_date": "That bill is already marked paid."}) from exc


def unpay_bill(payment: BillPayment) -> None:
    """Undo: delete the expense (and with it the payment mark)."""
    money.delete(payment.transaction)


def save_rule(rule: SplitRule) -> SplitRule:
    _check_owner(rule.owner, rule.to_wallet, rule.category)
    if (rule.to_wallet is None) == (rule.category is None):
        raise ValidationError({"to_wallet": "Send it to a wallet or spend it on a category."})
    if rule.category is not None and rule.category.kind != "expense":
        raise ValidationError({"category": "Pick an expense category."})
    if rule.mode == SplitRule.Mode.PERCENT and not (0 < rule.value <= 100):
        raise ValidationError({"value": "Use a percent from 1 to 100."})
    if rule.value <= 0:
        raise ValidationError({"value": "Use an amount above zero."})
    rule.save()
    return rule


def preview_split(owner, amount: Decimal) -> list[dict]:
    rules = list(SplitRule.objects.filter(owner=owner, active=True).select_related("to_wallet"))
    try:
        parts = cycle.split_amounts(amount, [(r.mode, r.value) for r in rules])
    except ValueError as exc:
        raise ValidationError({"amount": str(exc)}) from exc
    return [{"rule": r, "amount": a} for r, a in zip(rules, parts, strict=True) if a > 0]


@db_transaction.atomic
def receive_pay(
    *, owner, amount: Decimal, wallet, date: dt.date, category=None, note: str = "Sahod"
) -> PaydaySplit:
    """Salary arrives: record the income, then apply every active split rule from that wallet.
    Transfers go to their wallet; category rules are spent right away (e.g. padala)."""
    income = money.record(
        owner=owner,
        kind="income",
        amount=amount,
        date=date,
        wallet=wallet,
        category=category,
        note=note,
    )
    split = PaydaySplit.objects.create(owner=owner, income=income)
    for line in preview_split(owner, amount):
        rule = line["rule"]
        if rule.to_wallet_id == wallet.pk:
            continue  # "move to the wallet it's already in": nothing to do
        txn = money.record(
            owner=owner,
            kind="transfer" if rule.to_wallet else "expense",
            amount=line["amount"],
            date=date,
            wallet=wallet,
            to_wallet=rule.to_wallet,
            category=rule.category,
            note=rule.name,
        )
        SplitLine.objects.create(split=split, rule=rule, transaction=txn)
    return split


def save_goal(goal: Goal) -> Goal:
    _check_owner(goal.owner, goal.wallet)
    if not goal.name.strip():
        raise ValidationError({"name": "Give your goal a name."})
    goal.name = goal.name.strip()
    goal.save()
    return goal
