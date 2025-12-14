from django.db import models

# Create your models here.
class WorkoutType(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "workout_types"   # ← exact name from your existing DB
        managed = False              # Django won’t create/migrate this table

    def __str__(self) -> str:
        return self.name


class Workout(models.Model):
    workout_name = models.CharField(max_length=120)
    workout_type = models.ForeignKey(WorkoutType, on_delete=models.PROTECT)

    class Meta:
        db_table = "workouts"
        managed = False

    def __str__(self) -> str:
        return self.workout_name


class Run(models.Model):
    datetime = models.DateTimeField(db_index=True)
    workout = models.ForeignKey(Workout, on_delete=models.PROTECT)
    distance_m = models.IntegerField()          # store meters (int)
    duration_sec = models.IntegerField()        # store seconds (int)
    avg_power = models.IntegerField(null=True, blank=True)
    avg_hr = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "runs"            # ← existing table name
        managed = False
        ordering = ["-datetime"]  # newest first

    def __str__(self):
        return f"{self.datetime} – {self.workout.workout_name}"
