from django.db import models
from django.db.models import Sum
from django.utils.datetime_safe import datetime


class GamificationInterface(models.Model):
    """
    A user should have a foreign key to a GamificationInterface to keep track of all gamification
    related objects.
    
    game_tracking = ForeignKey(GamificationInterface)
    """

    @property
    def points(self):
        return PointChange.objects.filter(interface=self).aggregate(Sum('amount'))['amount__sum'] or 0


class Category(models.Model):
    """

    """
    name = models.CharField(max_length=128, null=True, blank=True)
    description = models.TextField(null=True, blank=True)


class BadgeDefinition(models.Model):
    """

    """
    name = models.CharField(max_length=128)
    description = models.TextField(null=True, blank=True)
    progression_target = models.IntegerField(null=True, blank=True)
    next_badge = models.ForeignKey('self', null=True)
    category = models.ForeignKey(Category, null=True)
    points = models.BigIntegerField(null=True, blank=True)

    def save(self, *args, **kwargs):
        """
        We made this method expensive as it is likely to be used very rarely (creation of new types of Badges).
        By doing so we save having to do expensive joins for filters that look at the badge name or definition.

        This may be simplified in the future if users opt to use Badge.objects.filter(badge_definition__name=...)
        whereas we wanted it to be simpler syntax as the current Badge.objects.filter(name=...)

        :param args: 
        :param kwargs: 
        :return: 
        """

        # If this is a new BadgeDefinition
        if self.pk is None:
            super(BadgeDefinition, self).save(*args, **kwargs)

            # Create Badges for all GamificationInterfaces
            for interface in GamificationInterface.objects.all():
                Badge.objects.create(
                    interface=interface,
                    name=self.name,
                    description=self.description,
                    progression=Progression.objects.create(target=self.progression_target) if self.progression_target
                    else None,
                    category=self.category,
                    points=self.points,
                    badge_definition=self
                )
                if self.next_badge:
                    current_badge = Badge.objects.filter(
                        interface=interface,
                        badge_definition=self
                    ).first()
                    current_badge.next_badge = Badge.objects.filter(
                        interface=interface,
                        badge_definition=self.next_badge
                    ).first()
                    current_badge.save()

        else:
            super(BadgeDefinition, self).save(*args, **kwargs)

            # Update all Badges that use this definition
            # unfortunately we need to loop rather than using .update because we need to update all the
            # Progression objects as well
            for badge in Badge.objects.filter(badge_definition=self):
                badge.name = self.name
                badge.description = self.description

                if badge.progression:
                    if self.progression_target is None:
                        temp = badge.progression
                        badge.progression = None
                        temp.delete()
                    else:
                        badge.progression.target = self.progression_target
                        badge.progression.save()
                if self.next_badge:
                    badge.next_badge = Badge.objects.filter(
                        interface=badge.interface,
                        badge_definition=self.next_badge
                    ).first()

                badge.category = self.category
                badge.points = self.points
                badge.save()


class Progression(models.Model):
    """
    
    """
    progress = models.IntegerField(default=0, null=False, blank=False)
    target = models.IntegerField(null=False, blank=False)

    def increment(self):
        self.progress += 1

    @property
    def finished(self):
        return self.progress >= self.target


class PointChange(models.Model):
    """

    """
    amount = models.BigIntegerField(null=False, blank=False)
    interface = models.ForeignKey(GamificationInterface)
    time = models.DateTimeField(auto_now_add=True)


class Badge(models.Model):
    """

    """
    badge_definition = models.ForeignKey(BadgeDefinition)
    acquired = models.BooleanField(default=False)
    interface = models.ForeignKey(GamificationInterface)

    # These should be populated by the BadgeDefinition that generates this
    name = models.CharField(max_length=128)
    description = models.TextField(null=True, blank=True)
    progression = models.ForeignKey(Progression, null=True)
    next_badge = models.ForeignKey('self', null=True)
    category = models.ForeignKey(Category, null=True)
    points = models.BigIntegerField(null=True, blank=True)

    def increment(self):
        if self.progression:
            self.progression.increment()
            if self.progression.finished:
                self.acquired = True

    def award(self):
        if not self.progression or self.progression.finished:
            self.acquired = True
            if self.points is not None:
                PointChange.objects.create(
                    amount=self.points,
                    interface=self.interface
                )


class UnlockableDefinition(models.Model):
    """

    """
    name = models.CharField(max_length=128)
    description = models.TextField(null=True, blank=True)
    points_required = models.BigIntegerField(null=False, blank=False)

    def save(self, *args, **kwargs):
        """
        We made this method expensive as it is likely to be used very rarely (creation of new types of Unlockables).
        By doing so we save having to do expensive joins for filters that look at the unlockable name or definition.

        This may be simplified in the future if users opt to
        use Unlockable.objects.filter(unlockable_definition__name=...)
        whereas we wanted it to be simpler syntax as the current Unlockable.objects.filter(name=...)

        :param args: 
        :param kwargs: 
        :return: 
        """

        # If this is a new UnlockableDefinition
        if self.pk is None:
            super(UnlockableDefinition, self).save(*args, **kwargs)

            # Create Unlockables for all GamificationInterfaces
            for interface in GamificationInterface.objects.all():
                Unlockable.objects.create(
                    interface=interface,
                    name=self.name,
                    description=self.description,
                    points_required=self.points_required,
                    unlockable_definition=self
                )

        else:
            super(UnlockableDefinition, self).save(*args, **kwargs)

            # Update all Unlockable that use this definition
            Unlockable.objects.filter(unlockable_definition=self).update(
                name=self.name,
                description=self.description,
                points_required=self.points_required
            )


class Unlockable(models.Model):
    """

    """
    unlockable_definition = models.ForeignKey(UnlockableDefinition)
    acquired = models.BooleanField(default=False)
    interface = models.ForeignKey(GamificationInterface)

    # These should be populated by the UnlockableDefinition that generates this
    name = models.CharField(max_length=128)
    points_required = models.BigIntegerField(null=False, blank=False)
    description = models.TextField(null=True, blank=True)


import django_gamification.signals
