"""Create the demo user with ~6 weeks of believable, entirely fake money activity.

    python manage.py seed_demo          # create the demo user if missing
    python manage.py seed_demo --reset  # delete the demo user's data and recreate it
    python manage.py seed_demo --reset --wipe-visitors  # public demo: also delete sign-ups

Without --wipe-visitors only the demo user is touched. The public demo (bin/start.sh with
DEMO_MODE) wipes visitor accounts on every start: nothing a visitor types in is kept for long.
Staff and superuser accounts are never deleted.
"""

import datetime as dt
import random
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from faker import Faker

from accounts import services as accounts
from money import selectors
from money import services as money
from money.models import Category, Wallet
from paluwagan import selectors as paluwagan_selectors
from paluwagan import services as paluwagan
from paluwagan.models import Paluwagan
from planning import cycle
from planning import services as planning
from planning.models import Bill, Goal, SplitRule
from utang import services as utang

D = Decimal
# (note, category, low, high, wallets) - everyday spending in pesos
DAILY = [
    ("kape", "Food & drinks", 120, 190, ["GCash", "Cash"]),
    ("jeep", "Transport", 13, 30, ["Cash"]),
    ("lunch", "Food & drinks", 110, 260, ["Cash", "GCash"]),
    ("grab", "Transport", 160, 420, ["GCash", "Maya"]),
    ("merienda", "Food & drinks", 40, 120, ["Cash"]),
    ("milk tea", "Food & drinks", 120, 180, ["GCash", "Maya"]),
    ("load", "Load & data", 50, 299, ["GCash"]),
    ("palengke", "Groceries", 350, 1200, ["Cash"]),
    ("puregold", "Groceries", 800, 2600, ["Maya", "Bank"]),
    ("gamot", "Health", 90, 450, ["Cash", "GCash"]),
    ("shopee", "Shopping", 199, 1200, ["GCash", "Maya"]),
    ("sine", "Fun", 350, 600, ["GCash"]),
]
BILLS = [
    ("Rent", "8500", 5, "Bank"),
    ("Meralco", "2380", 20, "GCash"),
    ("Internet", "1699", 25, "GCash"),
    ("Spotify", "149", 12, "Maya"),
]
SALARY = D("18500")


class Command(BaseCommand):
    help = "Create (or with --reset, recreate) the demo user with fake activity."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Recreate the demo user's data.")
        parser.add_argument(
            "--wipe-visitors",
            action="store_true",
            help="Also delete every other non-staff account (public demo only).",
        )

    @transaction.atomic
    def handle(self, *args, reset=False, wipe_visitors=False, **options):
        User = get_user_model()
        if wipe_visitors:
            visitors = User.objects.filter(is_staff=False, is_superuser=False).exclude(
                username=settings.DEMO_USERNAME
            )
            count = visitors.count()
            visitors.delete()
            self.stdout.write(f"Removed {count} visitor account(s).")
        existing = User.objects.filter(username=settings.DEMO_USERNAME).first()
        if existing and not reset:
            self.stdout.write("Demo user already exists (use --reset to recreate it).")
            return
        if existing:
            existing.delete()

        rng = random.Random(2026)  # same demo every time
        fake = Faker("en_PH")
        fake.seed_instance(2026)
        user = accounts.sign_up(username=settings.DEMO_USERNAME, password=settings.DEMO_PASSWORD)
        user.first_name = fake.first_name()
        user.save(update_fields=["first_name"])
        self.populate(user, rng)
        self.stdout.write(self.style.SUCCESS(f"Demo user ready: {settings.DEMO_USERNAME}"))

    def populate(self, user, rng: random.Random) -> None:
        wallets = {w.name: w for w in Wallet.objects.filter(owner=user)}
        cats = {c.name: c for c in Category.objects.filter(owner=user)}
        today = timezone.localdate()
        start = today - dt.timedelta(days=42)

        # Opening balances: what was there before the history starts.
        for name, amount in (
            ("Cash", "1800"),
            ("GCash", "2400"),
            ("Maya", "2650"),
            ("Bank", "9200"),
            ("Savings", "15000"),
        ):
            wallets[name].opening_balance = D(amount)
            wallets[name].save(update_fields=["opening_balance"])

        schedule = planning.schedule_for(user)
        schedule.expected_pay = SALARY
        schedule.keep_aside = D("1000")
        planning.save_schedule(schedule)

        for name, amount, day, wallet in BILLS:
            Bill.objects.create(
                owner=user,
                name=name,
                amount=D(amount),
                due_day=day,
                wallet=wallets[wallet],
                category=cats["Bills"],
            )
        SplitRule.objects.create(
            owner=user,
            name="Ipon",
            mode="percent",
            value=D("15"),
            to_wallet=wallets["Savings"],
            sort_order=1,
        )
        SplitRule.objects.create(
            owner=user,
            name="Padala kay Nanay",
            mode="fixed",
            value=D("2500"),
            category=cats["Padala"],
            sort_order=2,
        )
        SplitRule.objects.create(
            owner=user,
            name="Pang-gastos sa GCash",
            mode="fixed",
            value=D("4000"),
            to_wallet=wallets["GCash"],
            sort_order=3,
        )

        paydays = [
            d for d in cycle.paydays_around(schedule.as_schedule(), today) if start <= d <= today
        ]
        # Bills due before the current cycle are paid on their due date; this cycle's stay open,
        # so the demo shows bills being set aside.
        cycle_start = max(paydays) if paydays else start
        bills = list(Bill.objects.filter(owner=user))
        for day in (start + dt.timedelta(days=n) for n in range((today - start).days + 1)):
            if day in paydays:
                planning.receive_pay(
                    owner=user,
                    amount=SALARY,
                    wallet=wallets["Bank"],
                    date=day,
                    category=cats["Salary"],
                )
            for bill in bills:
                if day < cycle_start and day in cycle.bill_due_dates(bill.due_day, day, day):
                    wallet = self.funded(user, [bill.wallet.name, "Bank"], bill.amount, wallets)
                    planning.pay_bill(bill, due_date=day, paid_on=day, wallet=wallet)
            self.spend_day(user, day, today, wallets, cats, rng)

        money.record(
            owner=user,
            kind="income",
            amount=D("3500"),
            date=today - dt.timedelta(days=9),
            wallet=wallets["GCash"],
            category=cats["Side hustle"],
            note="logo commission",
        )

        # Utang: a friend paying back in parts, and a short loan due before payday.
        pedro = utang.create(
            owner=user,
            person="Pedro",
            direction="lent",
            amount=D("1500"),
            date=today - dt.timedelta(days=20),
            wallet=self.funded(user, ["GCash"], D("1500"), wallets),
            note="pang-tuition",
        )
        utang.add_payment(
            pedro, amount=D("500"), date=today - dt.timedelta(days=6), wallet=wallets["GCash"]
        )
        utang.create(
            owner=user,
            person="Ate Lyn",
            direction="borrowed",
            amount=D("2000"),
            date=today - dt.timedelta(days=3),
            due_date=today + dt.timedelta(days=8),
            wallet=wallets["Cash"],
        )

        # Ipon goals, saved in the Savings wallet (filled in date order).
        for name, emoji, target, months in (
            ("Emergency fund", "🛟", "30000", 3),
            ("Siargao trip", "🏝️", "15000", 7),
        ):
            planning.save_goal(
                Goal(
                    owner=user,
                    name=name,
                    emoji=emoji,
                    target=D(target),
                    target_date=today + dt.timedelta(days=30 * months),
                    wallet=wallets["Savings"],
                )
            )

        # A paluwagan at the office: a share every payday, past shares paid, pot in round 4.
        group = paluwagan.save(
            Paluwagan(
                owner=user,
                name="Office paluwagan",
                share=D("1000"),
                members=6,
                my_turn=4,
                frequency="payday",
                start_date=paydays[0] if paydays else today,
                wallet=wallets["Bank"],
            )
        )
        for row in paluwagan_selectors.rounds(group):
            if row["date"] <= today and self.funded(user, ["Bank"], group.share, wallets):
                paluwagan.record(
                    group, kind="contribution", round_number=row["round"], date=row["date"]
                )

    @staticmethod
    def funded(user, names, amount, wallets):
        """The first of these wallets that can cover `amount` (people don't overdraw GCash)."""
        balances = selectors.balances(user)
        for name in [*names, "Bank", "GCash", "Cash", "Maya"]:
            if balances[wallets[name].pk] >= amount:
                return wallets[name]
        return None

    def spend_day(self, user, day, today, wallets, cats, rng) -> None:
        # Today stays light (one jeepney ride) so the demo opens with room to spend.
        picks = rng.sample(DAILY, rng.randint(1, 3)) if day < today else [DAILY[1]]
        for note, cat, low, high, wallet_names in picks:
            if note in ("puregold", "shopee", "sine") and rng.random() < 0.7:
                continue  # big-ticket items are occasional
            amount = D(rng.randint(low, high))
            wallet = self.funded(user, rng.sample(wallet_names, len(wallet_names)), amount, wallets)
            if wallet is None:
                continue  # broke until sahod: skip it, like a real person would
            money.record(
                owner=user,
                kind="expense",
                amount=amount,
                date=day,
                wallet=wallet,
                category=cats[cat],
                note=note,
            )
        if day.weekday() == 0 and day < today and self.funded(user, ["Bank"], D("1500"), wallets):
            money.record(
                owner=user,
                kind="transfer",
                amount=D("1500"),
                date=day,
                wallet=wallets["Bank"],
                to_wallet=wallets["Cash"],
                note="ATM",
            )
