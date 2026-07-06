import scala.collection.mutable
import io.shiftleft.codepropertygraph.generated.nodes.{Call, Method, MethodParameterIn}
import java.util.regex.Pattern

def loadParams(path: String): Map[String, Seq[String]] = {
  val decoder = java.util.Base64.getDecoder
  val source = scala.io.Source.fromFile(path)
  try {
    source.getLines().map(_.trim).filter(_.nonEmpty).toList.flatMap { line =>
      val tab = line.indexOf('\t')
      if (tab < 0) None
      else Some((line.substring(0, tab), new String(decoder.decode(line.substring(tab + 1)), "UTF-8")))
    }.groupBy(_._1).map { case (k, kvs) => (k, kvs.map(_._2)) }
  } finally source.close()
}

def esc(s: String): String = {
  if (s == null) ""
  else {
    val sb = new StringBuilder
    s.foreach {
      case '\\' => sb.append("\\\\")
      case '"'  => sb.append("\\\"")
      case '\n' => sb.append("\\n")
      case '\r' => sb.append("\\r")
      case '\t' => sb.append("\\t")
      case '\b' => sb.append("\\b")
      case '\f' => sb.append("\\f")
      case c if c < 0x20 => sb.append("\\u%04x".format(c.toInt))
      case c => sb.append(c)
    }
    sb.toString
  }
}

def findOpenRedirectFlows(paramsPath: String, outputPath: String): Unit = {
  val params = loadParams(paramsPath)
  val lines = params.getOrElse("pair", Seq.empty).toArray
  val sourceAnnotations = params.getOrElse("sourceAnnotation", Nil).map(_.stripPrefix("@")).toSet
  val requestAccessors = params.getOrElse("requestAccessor", Nil).toSet

  val frameworkTypeMarkers = Seq(
    "HttpServletResponse",
    "ServletResponse",
    "HttpServletRequest",
    "ServletRequest",
    "HttpSession",
    "javax.ws.rs.core.Response",
    "jakarta.ws.rs.core.Response",
    "org.springframework.ui.Model",
    "org.springframework.ui.ModelMap",
    "org.springframework.validation.BindingResult",
    "org.springframework.validation.Errors",
    "org.springframework.web.servlet.mvc.support.RedirectAttributes",
    "org.springframework.web.util.UriComponentsBuilder",
    "java.security.Principal",
    "org.springframework.security.core.Authentication",
    "java.util.Locale"
  )

  def typeContains(typeFullName: String, marker: String): Boolean =
    typeFullName != null && (typeFullName == marker || typeFullName.endsWith("." + marker) || typeFullName.contains(marker))

  def isFrameworkParam(p: MethodParameterIn): Boolean =
    frameworkTypeMarkers.exists(marker => typeContains(p.typeFullName, marker))

  def isAnnotatedRequestParam(p: MethodParameterIn): Boolean =
    sourceAnnotations.nonEmpty && p.annotation.name(sourceAnnotations.toSeq: _*).nonEmpty

  def isRequestControlledParam(p: MethodParameterIn): Boolean =
    p.name != "this" && !isFrameworkParam(p) && (isAnnotatedRequestParam(p) || Option(p.name).exists(_.nonEmpty))

  def isRequestAccessor(c: Call): Boolean = {
    val code = Option(c.code).getOrElse("")
    val methodFullName = Option(c.methodFullName).getOrElse("")
    requestAccessors.contains(c.name) &&
      (methodFullName.contains("HttpServletRequest") || code.contains("." + c.name + "("))
  }

  def nonReceiverArgs(c: Call) = {
    val receiverIds = c.receiver.l.map(_.id).toSet
    c.argument.l.filterNot(arg => receiverIds.contains(arg.id)).sortBy(_.argumentIndex)
  }

  def isLocationLiteral(code: String): Boolean = {
    val normalized = Option(code).getOrElse("").trim.stripPrefix("\"").stripSuffix("\"")
    normalized.equalsIgnoreCase("Location")
  }

  def redirectTargetArgs(c: Call) = {
    val args = nonReceiverArgs(c)
    val name = Option(c.name).getOrElse("")
    if (name == "<operator>.addition") {
      (c :: args).distinct
    } else if (Set("setHeader", "addHeader", "header", "putHeader", "add", "set").contains(name)) {
      val locationIdx = args.indexWhere(arg => isLocationLiteral(arg.code))
      if (locationIdx >= 0 && locationIdx + 1 < args.size) List(args(locationIdx + 1))
      else args.takeRight(1)
    } else if (name == "sendRedirect" && args.size >= 2) {
      List(args.last)
    } else {
      args.take(1)
    }
  }

  def simpleIdentifier(code: String): Option[String] = {
    val value = Option(code).getOrElse("").trim
    if (value.matches("[A-Za-z_$][A-Za-z0-9_$]*")) Some(value) else None
  }

  def namesInExpr(expr: io.shiftleft.codepropertygraph.generated.nodes.Expression): Set[String] =
    (expr.ast.isIdentifier.name.l ++ simpleIdentifier(expr.code).toList).toSet

  def hasRequestAccessor(expr: io.shiftleft.codepropertygraph.generated.nodes.Expression): Boolean =
    expr.ast.isCall.exists(isRequestAccessor)

  def sourceSummary(method: Method) = {
    val params = method.parameter.filter(isRequestControlledParam).l
    val labels = mutable.Map[String, String]()
    val flows = mutable.Map[String, String]()

    params.foreach { p =>
      val kind =
        p.annotation.name.l.find(a => sourceAnnotations.contains(a)).map("@" + _).getOrElse("request parameter")
      labels.put(p.name, kind)
      labels.put(p.code, kind)
      flows.put(p.name, s"$kind ${p.name}")
    }

    (mutable.LinkedHashSet(params.map(_.name): _*), labels.toMap, flows)
  }

  def assignmentTarget(c: Call): Option[String] =
    c.argument.argumentIndex(1).code.headOption.flatMap(simpleIdentifier)

  def assignmentRhs(c: Call) =
    c.argument.argumentIndex(2).headOption

  def propagateLocalAssignments(
      method: Method,
      sinkLine: Int,
      initialTainted: mutable.LinkedHashSet[String],
      initialFlows: mutable.Map[String, String]
  ): (mutable.LinkedHashSet[String], mutable.Map[String, String]) = {
    val tainted = mutable.LinkedHashSet[String]() ++ initialTainted
    val flows = mutable.Map[String, String]() ++ initialFlows
    val assignments = method.call.name("<operator>.assignment").l
      .filter(c => c.lineNumber.exists(_ <= sinkLine))
      .sortBy(c => c.lineNumber.getOrElse(0))

    var changed = true
    while (changed) {
      changed = false
      assignments.foreach { assignment =>
        val lhsOpt = assignmentTarget(assignment)
        val rhsOpt = assignmentRhs(assignment)
        (lhsOpt, rhsOpt) match {
          case (Some(lhs), Some(rhs)) if !tainted.contains(lhs) =>
            val rhsNames = namesInExpr(rhs)
            val matched = rhsNames.find(tainted.contains)
            if (matched.isDefined || hasRequestAccessor(rhs)) {
              tainted += lhs
              val sourceFlow = matched.flatMap(flows.get).getOrElse(rhs.code)
              flows.put(lhs, s"$sourceFlow -> $lhs = ${rhs.code}")
              changed = true
            }
          case _ =>
        }
      }
    }
    (tainted, flows)
  }

  def flowIntoTarget(
      target: io.shiftleft.codepropertygraph.generated.nodes.Expression,
      tainted: mutable.LinkedHashSet[String],
      flows: mutable.Map[String, String]
  ): Option[(String, String)] = {
    val targetNames = namesInExpr(target)
    targetNames.find(tainted.contains).map { name =>
      val sourceFlow = flows.getOrElse(name, name)
      val summary = if (target.code == name) sourceFlow else s"$sourceFlow -> ${target.code}"
      (name, summary)
    }.orElse {
      if (hasRequestAccessor(target)) Some((target.code, target.code)) else None
    }
  }

  val results = mutable.ArrayBuffer[String]()

  for (line <- lines) {
    val parts = line.split("\t")
    if (parts.length >= 3) {
      val sourceFullName = parts(0)
      val lineNumber = parts(1).toInt
      val fileName = parts(2)
      val regexFileName = ".*" + Pattern.quote(fileName) + "$"

      try {
        val sourceOpt = cpg.method.fullNameExact(sourceFullName).headOption
        val calls = cpg.file.name(regexFileName).method.call.filter(_.lineNumber.exists(_ == lineNumber)).l

        if (sourceOpt.isDefined && calls.nonEmpty) {
          val source = sourceOpt.get
          val (requestSources, labels, initialFlows) = sourceSummary(source)
          val localCalls = calls.filter(call => call.method.fullName == source.fullName)
          var emitted = false

          for (call <- localCalls if !emitted) {
            val targetArgs = redirectTargetArgs(call)
            if (targetArgs.nonEmpty && requestSources.nonEmpty) {
              val (tainted, flows) = propagateLocalAssignments(source, lineNumber, requestSources, initialFlows)
              val targetFlow = targetArgs.flatMap(target => flowIntoTarget(target, tainted, flows)).headOption
              if (targetFlow.isDefined) {
                val (sourceParam, flowSummarySuffix) = targetFlow.get
                val sourceKind = labels.getOrElse(sourceParam, if (sourceParam.contains("(")) "request accessor" else "request parameter")
                val sinkArg = targetArgs.headOption.map(_.code).getOrElse("")
                val flowSummary = s"$flowSummarySuffix -> ${Option(call.code).getOrElse("")}"
                results.append(
                  s"""{"source":"${esc(sourceFullName)}","lineNumber":$lineNumber,"fileName":"${esc(fileName)}","requestControlled":true,"sinkArgument":"${esc(sinkArg)}","sourceParam":"${esc(sourceParam)}","sourceKind":"${esc(sourceKind)}","flowSummary":"${esc(flowSummary)}","flowConfidence":"cpg-target-argument","sinkCode":"${esc(call.code)}"}"""
                )
                emitted = true
              }
            }
          }

          if (!emitted && localCalls.nonEmpty) {
            val sinkArg = localCalls.flatMap(redirectTargetArgs).headOption.map(_.code).getOrElse("")
            results.append(
              s"""{"source":"${esc(sourceFullName)}","lineNumber":$lineNumber,"fileName":"${esc(fileName)}","requestControlled":false,"sinkArgument":"${esc(sinkArg)}","flowSummary":"${esc("No request-controlled source reaches the redirect target argument in the CPG data-flow query.")}","flowConfidence":"not_request_controlled","sinkCode":"${esc(localCalls.head.code)}"}"""
            )
          }
        }
      } catch {
        case e: Exception =>
          println(s"[open-redirect-flow] error processing $sourceFullName -> $fileName:$lineNumber : ${e.getMessage}")
      }
    }
  }

  val writer = new java.io.PrintWriter(new java.io.File(outputPath))
  try { writer.write(results.mkString("[", ",", "]")) } finally { writer.close() }
}
