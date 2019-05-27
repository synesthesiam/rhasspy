<template>
    <div class="container">
        <table class="table table-striped">
            <thead>
                <tr>
                    <th>Component</th>
                    <th>Problem</th>
                    <th>Description</th>
                </tr>
            </thead>
            <tbody>
                <tr v-for="(problem, i) in this.problemList" v-bind:key="i">
                    <td>{{ problem.actor }}</td>
                    <td>{{ problem.name }}</td>
                    <td>{{ problem.description }}</td>
                </tr>
            </tbody>
        </table>
    </div> <!-- container -->
</template>

<script>
 export default {
     name: 'Problems',
     data: function() {
         return {
             problemList: []
         }
     },
     props: {
         problems: Object
     },
     watch: {
         problems: function() {
             for (var actor in this.problems) {
                 var actorProblems = this.problems[actor]
                 for (var problem in actorProblems) {
                     this.problemList.push({
                         actor: actor,
                         name: problem,
                         description: actorProblems[problem]
                     })
                 }
             }
         }
     }
 }
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
